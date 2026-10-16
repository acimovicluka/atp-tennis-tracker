# start from the official python image, it already has linux, python and pip inside
# slim is the smaller version without extra stuff we don't need
FROM python:3.12-slim

# everything below happens in the /app folder inside the container
WORKDIR /app

# install the packages first, on their own
# docker remembers every step, so this only runs again when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# now copy the rest of the code
COPY . .

# what runs when the container starts
# 0.0.0.0 means listen to requests from outside the container too, not only from inside
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
