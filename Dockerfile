# Use the official Python image from Docker Hub
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the Python files into the container's working directory
COPY . /app

# Install any dependencies specified in the requirements.txt file
RUN pip install --no-cache-dir -r requirements.txt

# Set the command to run your main script
CMD ["python", "__main__.py"]