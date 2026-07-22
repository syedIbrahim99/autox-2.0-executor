######## Agent creation ########

#Trigger command:

curl -X POST http://10.0.0.131:31467/deploy-agent   -H "Content-Type: application/json"   -d '{
    "AGENT_NAME": "scenario-01-salesforce-simple-agent",
    "AGENT_ENDPOINT": "http://10.0.0.100:8082/artifactory/autox-agents-2.0-dev/scenario_01_salesforce_simple_agent-0.1.0-py3-none-any.whl"
  }'

## Response got from health check:

{"deployed_url":"http://autox:eyJ2ZXIiOiIyIiwidHlwIjoiSldUIiwiYWxnIjoiUlMyNTYiLCJraWQiOiJoVWkyX2ttdzFDQ3haR0IwUVdqWWYtSUFMZnRJenRSWDd6Yjd3RjBPemRnIn0.eyJzdWIiOiJqZmZlQDAwMFwvdXNlcnNcL2F1dG94Iiwic2NwIjoiYXBwbGllZC1wZXJtaXNzaW9uc1wvYWRtaW4gYXBpOioiLCJhdWQiOlsiamZydEAqIiwiamZtZEAqIl0sImlzcyI6ImpmZmVAMDAwIiwiaWF0IjoxNzgxNzY2MzY4LCJqdGkiOiI3OTBlY2M1OS0xZWVlLTQ4NjMtODg2NC1kZTNiZDk1YzU0MGUifQ.RGWATiP0PSK21hRxQqyVl1M4kLIBjAAICi8s3DjCug6zpk4vIRuawCy2Oifmb4r5HOZP08bRHHu5-m20z8nC7o3fwxcWlPPXjz8umw7jayyUsi-RL0qqsC-lSuRaWD_LkGcTUKGAH003QOLfJKQYhTJ-Xljw5wRnm9MHQd5JBUJRczx7N7Ir41RH8Kv5TiMYZykIkd25Aqkk8TVYhzGLOTOvjlL-g_MvOnYhVA_l1Ep4Hg-q8bhdTy02XpIbMbZCr6e8DWN8bTllT1J_XKjA4NFUkHtVN3eZiIGLF4Cq4-1fJte6AGZNqk6H1WZuLuWIhh2VatJkADiaY1pXA9KClA@10.0.0.100:8082/artifactory/autox-agents-2.0-dev/scenario_01_salesforce_simple_agent-0.1.0-py3-none-any.whl","executed_command":"scenario_01_salesforce_simple_agent","k8s_agent_name":"scenario-01-salesforce-simple-agent","original_agent_name":"scenario-01-salesforce-simple-agent","service_endpoint":"http://scenario-01-salesforce-simple-agent-svc.autox-v2-exec.svc.cluster.local:8080","status":"success"}

######## Agent Deletion ########

#Trigger command:

curl -X POST http://10.0.0.131:31467/delete-agent    -H "Content-Type: application/json"    -d '{
    "AGENT_NAME": "scenario-01-salesforce-simple-agent"
  }'

## Response got after deletion:

{"k8s_agent_name":"scenario-01-salesforce-simple-agent","message":"Agent 'scenario-01-salesforce-simple-agent' and its service were successfully deleted.","status":"success"}
