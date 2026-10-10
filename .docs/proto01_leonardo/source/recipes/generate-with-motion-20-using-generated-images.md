---
updatedAt: 2025-09-03T05:59:46.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Motion 2.0 Using Generated Images

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations-image-to-video \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "imageType": "GENERATED",
  "isPublic": false,
  "imageId": "8815cca4-4cf7-4f21-aec4-00f8977f61d5",
  "prompt": "A cat roaring like a tiger",
  "frameInterpolation": true,
  "promptEnhance": true,
  "elements": [
   	 {
    	 "akUUID": "ece8c6a9-3deb-430e-8c93-4d5061b6adbf",
    	 "weight":1
   	 }
  ]
}
'

# Wait for a few seconds for images to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

# Create a video generation

<!-- shell@1-15 -->

Generate an image using a generated image.

Replace <YOUR_API_KEY> with your API key.

imageId is from an image generated in Leonardo.Ai. Refer to Image Generation guide on how to generate images and grabbing the image ID from the response.

The response will contain a generationId attribute that you will need in the next step.

# Get the video generation

<!-- shell@19-22 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain the URL links for the video to download