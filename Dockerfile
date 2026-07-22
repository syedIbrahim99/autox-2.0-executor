FROM privaterepo.com:5000/base:python3.14
ADD autox-source /autox-source
WORKDIR /autox-source
#RUN pip3.14 install -r requirements.txt
RUN pip3.14 install --ignore-installed blinker -r requirements.txt
# python3.14 app.py --host 0.0.0.0 --port 8080
