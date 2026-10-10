---
updatedAt: 2025-09-03T05:59:48.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Motion 2.0 Fast 480p Using Text Prompts

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations-text-to-video \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "height": 480,
  "width": 832,
  "resolution": "RESOLUTION_480",
  "model": "MOTION2FAST",
  "prompt": "A dog walking on the beach",
  "frameInterpolation": true,
  "isPublic": false,
  "promptEnhance": true,
  "elements": [
   	 {
    	 "akUUID": "ece8c6a9-3deb-430e-8c93-4d5061b6adbf",
    	 "weight":1
   	 }
  ]
}
'

# Wait for a few seconds for video to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

# Create a video generation

<!-- shell@1-23 -->

Generate a video using a text input

Replace <YOUR_API_KEY> with your API key.

The response will contain a generationId attribute that you will need in the next step.

# Get the video generation

<!-- shell@25-30 -->

To fetch your video, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain the URL links for the video to download