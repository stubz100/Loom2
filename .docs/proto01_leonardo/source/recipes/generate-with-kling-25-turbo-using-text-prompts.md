---
updatedAt: 2026-02-09T07:19:17.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Kling 2.5 Turbo Using Text Prompts

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations-text-to-video \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{

    "prompt":"A dreamlike sea of flowers reminiscent of a movie scene, with a gentle breeze caressing the golden hour light and shadow. The most beautiful place in the world, captured in stunningly dynamic cinematography.",
    "duration": 5,
    "model": "KLING2_5",
    "height": 1080,
    "width": 1920,
    "resolution": "RESOLUTION_1080",
    "isPublic": false
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

Generate a video with Kling 2.5 Turbo  using a text input

Replace \<YOUR_API_KEY> with your API key.

The response will contain a generationId attribute that you will need in the next step.

# Get the video generation

<!-- shell@19-24 -->

To fetch your video, replace \<YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.