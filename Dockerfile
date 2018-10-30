FROM gorialis/discord.py:3.7-alpine-rewrite-full

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "lifesaver.cli"]
