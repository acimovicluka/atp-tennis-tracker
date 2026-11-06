# the Dockerfile is the recipe docker follows to build the image for this project
# one image is used for both the api and the fetcher, only the command at the start is different

# docker starts from the official python image, which already has linux, python and pip inside
# slim is the smaller version, without extra tools this project doesn't need
FROM python:3.12-slim

# every step below runs in the /app folder inside the container, docker makes the folder by itself
WORKDIR /app

# docker installs the packages first, on their own, before copying the code
# docker remembers every step as a layer (layer caching), and only redoes a step when its files change
# so when I only change api.py, docker reuses the installed packages and the build takes seconds instead of minutes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # --no-cache-dir keeps pip's download cache out of the image, so it stays smaller

# now docker copies the rest of the code, except what .dockerignore leaves out
COPY . .

# this is what the container runs when it starts: uvicorn with the api from api.py
# 0.0.0.0 tells uvicorn to listen to requests coming from outside the container too, not only from inside it
# the fetcher uses the same image but starts with python fetcher.py instead (see docker-compose.yml and k8s/fetcher.yaml)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
