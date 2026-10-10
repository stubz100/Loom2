---
updatedAt: 2026-02-10T06:03:19.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Kling 3.0 Using Text Prompts

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "model": "kling-3.0",
  "parameters": {
    "prompt": "Ocean waves crashing against rocky shore with seagulls and wind",
    "duration": 5,
    "width": 1440,
    "height": 1440,
    "mode": "RESOLUTION_1080",
    "motion_has_audio": true
  },
  "public": true
}
'

# Wait for a few seconds for video to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

# Create a video generation

<!-- shell@1-19 -->

Generate a video with Kling 3.0 using a text input

Replace \<YOUR_API_KEY> with your API key.

The response will contain a generationId attribute that you will need in the next step.

# Get the video generation

<!-- shell@23-26 -->

To fetch your video, replace \<YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.