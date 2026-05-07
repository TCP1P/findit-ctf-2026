FROM sagemath/sagemath:latest

RUN sudo apt-get update && sudo apt install -y socat python3 python3-pip

RUN mkdir /home/sage/ctf
COPY ./requirements.txt /home/sage/ctf

RUN sage -sh -c "python3 -m pip install -r /home/sage/ctf/requirements.txt"

RUN mkdir /home/sage/ctf/src
COPY ./chall.py /home/sage/ctf/src
COPY ./flag.txt /home/sage/ctf/src
COPY ./run.sh /home/sage/ctf/src
RUN sudo chmod +x /home/sage/ctf/src/run.sh

WORKDIR /home/sage/ctf/src

CMD ["./run.sh"]