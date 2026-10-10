---
updatedAt: 2025-10-15T16:00:13.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Veo3.1 Fast 1080p Using Text Prompts

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations-text-to-video \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "height": 1080,
    "width": 1920,
    "prompt":"a breathtaking, cinematic sequence of a massive crystal whale gliding through a vast night sky that behaves like a deep ocean. The whale’s body is sculpted from translucent, glimmering crystal—its surface faceted like a gemstone, catching moonlight and scattering it in radiant rainbow beams across the sky. Each movement creates soft refractions that dance across the clouds, making them ripple like bioluminescent waves.",
    "resolution": "RESOLUTION_1080",
    "duration": 8,
    "model": "VEO3_1FAST",
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

<!-- shell@1-16 -->

Generate a video with Veo3.1 Fast using a text input

Replace \<YOUR_API_KEY> with your API key.

The response will contain a generationId attribute that you will need in the next step.

# Get the video generation

<!-- shell@17-23 -->

To fetch your video, replace \<YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain the URL links for the video to download