FROM public.ecr.aws/lambda/python:3.11

RUN yum update --security -y && yum clean all
RUN pip install --upgrade pip setuptools wheel --no-cache-dir

COPY . ./
RUN pip install -r requirements.txt --upgrade --no-cache-dir

CMD ["app.lambda_handler"]

USER 1001
HEALTHCHECK --interval=600s --timeout=2s --retries=12 \
    CMD ["cat", "requirements.txt"]