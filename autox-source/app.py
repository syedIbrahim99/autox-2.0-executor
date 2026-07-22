import os
import time
import urllib3
import requests
import re
from flask import Flask, request, jsonify
from jinja2 import Template

# Disable InsecureRequestWarning for local K8s API calls
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# --- Strict Environment Configuration ---
NAMESPACE = os.environ["NAMESPACE"]
K8S_API_SERVER = os.environ["K8S_API_SERVER"]
KUBE_YAML_DIR = os.environ["KUBE_YAML_DIR"]
HOSTALIAS_IP = os.environ["HOSTALIAS_IP"]
AGENT_BASE_IMAGE = os.environ["AGENT_BASE_IMAGE"]
FLASK_PORT = int(os.environ["FLASK_PORT"])

# --- API Token (Injected from Kubernetes Secret) ---
API_TOKEN = os.environ["API_TOKEN"]

# --- Optional Environment Variables ---
NODE_SELECTOR = os.getenv("NODE_SELECTOR", "")
HOSTNAMES = os.getenv("HOSTNAMES", "")
JFROG_USER = os.getenv("JFROG_USER", "")
JFROG_TOKEN = os.getenv("JFROG_TOKEN", "")

# --- Default Command Setup ---
DEFAULT_AGENT_COMMAND = os.getenv("DEFAULT_AGENT_COMMAND", "")

# Template Paths
DEPLOYMENT_TEMPLATE = "/autox-source/kube-templates/agent-deployment.yaml"
SERVICE_TEMPLATE = "/autox-source/kube-templates/agent-service.yaml"

os.makedirs(KUBE_YAML_DIR, exist_ok=True)

def render_template(template_path: str, context: dict) -> str:
    with open(template_path) as f:
        template = Template(f.read())
    return template.render(**context)

def apply_k8s_resource(api_endpoint, yaml_data, resource_name, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/yaml",
    }

    requests.delete(
        f"{api_endpoint}/{resource_name}",
        headers=headers,
        verify=False
    )
    time.sleep(1)

    resp = requests.post(
        api_endpoint,
        headers=headers,
        data=yaml_data,
        verify=False
    )
    return resp

# --- NEW: Health Check Polling Function ---
def wait_for_agent_health(svc_name, namespace, timeout=120):
    """
    Polls the agent's Kubernetes service until it explicitly returns an HTTP 200 OK.
    """
    url = f"http://{svc_name}.{namespace}.svc.cluster.local:8080/health"

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            # ONLY return True if the agent explicitly returns a 200 OK
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            # Connection failed or refused... wait and try again
            pass

        time.sleep(3)

    return False

@app.route('/deploy-agent', methods=['POST'])
def deploy_agent():
    payload = request.json

    original_agent_name = payload.get("AGENT_NAME")
    provided_endpoint = payload.get("AGENT_ENDPOINT")

    if not original_agent_name or not provided_endpoint:
        return jsonify({"status": "error", "message": "Missing AGENT_NAME or AGENT_ENDPOINT"}), 400

    # --- Sanitize name for Kubernetes RFC 1123 compliance ---
    k8s_agent_name = re.sub(r'[^a-z0-9-]', '-', original_agent_name.lower())

    # --- NEW LOGIC: Handle full .whl URL dynamically ---
    # If the UI sends the full wheel URL, use it exactly as provided.
    # Otherwise, assume it is a directory and append the name.
    if provided_endpoint.endswith('.whl'):
        full_whl_url = provided_endpoint
    else:
        if not provided_endpoint.endswith('/'):
            provided_endpoint += '/'
        full_whl_url = f"{provided_endpoint}{original_agent_name}.whl"

    auth_whl_url = full_whl_url
    if JFROG_USER and JFROG_TOKEN and "://" in full_whl_url:
        protocol, rest_of_url = full_whl_url.split("://", 1)
        auth_whl_url = f"{protocol}://{JFROG_USER}:{JFROG_TOKEN}@{rest_of_url}"

    # --- Dynamic Command Generation ---
    base_module_name = re.split(r'-\d+\.', original_agent_name)[0].replace("-", "_")

    if payload.get("AGENT_COMMAND"):
        agent_command = payload.get("AGENT_COMMAND")
    elif DEFAULT_AGENT_COMMAND:
        agent_command = DEFAULT_AGENT_COMMAND.replace("<MODULE_NAME>", base_module_name)
    else:
        agent_command = base_module_name

    hostaliases_yaml = ""
    if HOSTNAMES:
        hostaliases_yaml = "\n".join(
            f"        - ip: \"{HOSTALIAS_IP}\"\n          hostnames:\n          - \"{h.strip()}\""
            for h in HOSTNAMES.split(",") if h.strip()
        )

    context = {
        "AGENT_NAME": k8s_agent_name,
        "ORIGINAL_AGENT_NAME": original_agent_name,
        "NAMESPACE": NAMESPACE,
        "NODE_SELECTOR": NODE_SELECTOR,
        "IMAGE": AGENT_BASE_IMAGE,
        "AGENT_ENDPOINT": auth_whl_url,
        "AGENT_COMMAND": agent_command,
        "HOSTALIASES": hostaliases_yaml
    }

    deployment_yaml = render_template(DEPLOYMENT_TEMPLATE, context)
    service_yaml = render_template(SERVICE_TEMPLATE, context)

    with open(f"{KUBE_YAML_DIR}/{k8s_agent_name}-deployment.yaml", "w") as f:
        f.write(deployment_yaml)
    with open(f"{KUBE_YAML_DIR}/{k8s_agent_name}-svc.yaml", "w") as f:
        f.write(service_yaml)

    deploy_api = f"{K8S_API_SERVER}/apis/apps/v1/namespaces/{NAMESPACE}/deployments"
    deploy_resp = apply_k8s_resource(deploy_api, deployment_yaml, k8s_agent_name, API_TOKEN)

    if deploy_resp.status_code not in (200, 201):
        return jsonify({"status": "failed", "error": deploy_resp.text}), 500

    svc_api = f"{K8S_API_SERVER}/api/v1/namespaces/{NAMESPACE}/services"
    svc_name = f"{k8s_agent_name}-svc"
    svc_resp = apply_k8s_resource(svc_api, service_yaml, svc_name, API_TOKEN)

    if svc_resp.status_code not in (200, 201):
        return jsonify({"status": "failed", "error": svc_resp.text}), 500

    # --- NEW: Wait for the agent to become healthy (HTTP 200) ---
    is_healthy = wait_for_agent_health(svc_name, NAMESPACE, timeout=120)

    if not is_healthy:
        return jsonify({
            "status": "failed",
            "error": "Deployment applied, but agent health check timed out waiting for HTTP 200. Pod might be failing or taking too long to start."
        }), 504

    return jsonify({
        "status": "success",
        "original_agent_name": original_agent_name,
        "k8s_agent_name": k8s_agent_name,
        "deployed_url": auth_whl_url,
        "executed_command": agent_command,
        "service_endpoint": f"http://{svc_name}.{NAMESPACE}.svc.cluster.local:8080"
    })

@app.route('/delete-agent', methods=['POST', 'DELETE'])
def delete_agent():
    payload = request.json
    original_agent_name = payload.get("AGENT_NAME")

    if not original_agent_name:
        return jsonify({"status": "error", "message": "Missing AGENT_NAME"}), 400

    # --- Sanitize name for Kubernetes RFC 1123 compliance ---
    k8s_agent_name = re.sub(r'[^a-z0-9-]', '-', original_agent_name.lower())

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/json",
    }

    # 1. Delete Deployment
    deploy_api = f"{K8S_API_SERVER}/apis/apps/v1/namespaces/{NAMESPACE}/deployments/{k8s_agent_name}"
    deploy_resp = requests.delete(deploy_api, headers=headers, verify=False)

    # 2. Delete Service
    svc_name = f"{k8s_agent_name}-svc"
    svc_api = f"{K8S_API_SERVER}/api/v1/namespaces/{NAMESPACE}/services/{svc_name}"
    svc_resp = requests.delete(svc_api, headers=headers, verify=False)

    # 200 = OK, 202 = Accepted (Deleting in background), 404 = Already deleted
    success_codes = (200, 202, 404)

    if deploy_resp.status_code not in success_codes or svc_resp.status_code not in success_codes:
        return jsonify({
            "status": "failed",
            "error": "Failed to delete Kubernetes resources",
            "deployment_status": deploy_resp.status_code,
            "service_status": svc_resp.status_code,
            "details": {
                "deployment": deploy_resp.text,
                "service": svc_resp.text
            }
        }), 500

    return jsonify({
        "status": "success",
        "message": f"Agent '{original_agent_name}' and its service were successfully deleted.",
        "k8s_agent_name": k8s_agent_name
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=FLASK_PORT)
