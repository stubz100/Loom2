---
updatedAt: 2025-12-11T06:59:20.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Kling O1 Using Image References

```python Python
import json
import requests
import time

api_key = "<YOUR_API_KEY>"
authorization = "Bearer %s" % api_key

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": authorization
}

# Get a presigned URL for uploading the first image
url = "https://cloud.leonardo.ai/api/rest/v1/init-image"
payload = {"extension": "jpg"}
response = requests.post(url, json=payload, headers=headers)
print("Get a presigned URL for uploading a start image: %s" % response.status_code)

# Upload first image via presigned URL
fields = json.loads(response.json()['uploadInitImage']['fields'])
url = response.json()['uploadInitImage']['url']
image_id_1 = response.json()['uploadInitImage']['id'] # For referencing later
image_file_path = "/project/workspace/cat.jpg"
files = {'file': open(image_file_path, 'rb')}
response = requests.post(url, data=fields, files=files)  # Header is not needed
print("Upload first image via presigned URL: %s" % response.status_code)

# Get a presigned URL for uploading the second image
url = "https://cloud.leonardo.ai/api/rest/v1/init-image"
payload = {"extension": "jpg"}
response = requests.post(url, json=payload, headers=headers)
print("Get a presigned URL for uploading a end image: %s" % response.status_code)

# Upload second image via presigned URL
fields = json.loads(response.json()['uploadInitImage']['fields'])
url = response.json()['uploadInitImage']['url']
image_id_2 = response.json()['uploadInitImage']['id'] # For referencing later
image_file_path = "/project/workspace/woman.jpg"
files = {'file': open(image_file_path, 'rb')}
response = requests.post(url, data=fields, files=files)  # Header is not needed
print("Upload start image via presigned URL: %s" % response.status_code)

# Generate video with image references
url = "https://cloud.leonardo.ai/api/rest/v2/generations"

payload = {
    "model": "kling-video-o-1",
    "public": False,
    "parameters": {
    "prompt": "The woman plays with the cat",
    "guidances": {
      "image_reference": [
        {
          "image": {
            "id": "%s" % image_id_1,
            "type": "UPLOADED"
          }
        },
        {
          "image": {
            "id": "%s" % image_id_2,
            "type": "UPLOADED"
          }
        }
      ]
    },
    "duration": 5,
    "width": 1080,
    "height": 1920
  }
}

response = requests.post(url, json=payload, headers=headers)

print("Generate video with an init image: %s" % response.status_code)
print(response.text)

# Get the generated video
generation_id = response.json()['generate']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(180)

response = requests.get(url, headers=headers)

print(response.text)
```

# Import libraries

<!-- python@1-3 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Set the API key in the header

<!-- python@5-12 -->

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace \<YOUR_API_KEY> with your API key.

# Upload image references

<!-- python@14-42 -->

This part requests presigned URLs from Leonardo.Ai and uses those to upload image references.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This request will return fields, presigned URL, and image ID.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

When upload is successful, the request will return a 204 success message with no content.

# Generate video with image references

<!-- python@44-77 -->

This part uses the uploaded files as image references to generate a new video.

This request returns a generation ID for fetching a video in the next step.

# Get the generated video

<!-- python@79-88 -->

This part fetches the video.

Note that generated video won't be immediately available.

For simplicity, this example sets a 180 second wait time before fetching the video.

For production use cases, use the API's webhook callback feature to receive a message containing the output.