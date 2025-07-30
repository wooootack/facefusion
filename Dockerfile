FROM python:3.12

ARG FACEFUSION_VERSION=3.3.2
ENV GRADIO_SERVER_NAME=0.0.0.0
ENV PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /facefusion

RUN apt-get update
RUN apt-get install curl -y
RUN apt-get install ffmpeg -y

# RUN git clone https://github.com/wooootack/facefusion.git --branch master --single-branch .
COPY ./ /facefusion
RUN python install.py --onnxruntime default --skip-conda
