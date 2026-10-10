---
updatedAt: 2025-10-30T04:31:16.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Hailuo 2.3 Using Text Prompts

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "hailuo-2_3",
    "public": false,
    "parameters": {
        "prompt": "rain on a city landscape",
        "duration": 6,
        "mode": "RESOLUTION_1080",
        "width": 1920,
        "height": 1080
    }
}
'

# Wait for a few seconds for video to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

# Create a video generation

<!-- shell@1-17 -->

Generate a video with Hailuo 2.3 using a text input

Replace \<YOUR_API_KEY> with your API key.

The response will contain a generationId attribute that you will need in the next step.

# Get the video generation

<!-- shell@19-24 -->

To fetch your video, replace \<YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain the URL links for the video to download