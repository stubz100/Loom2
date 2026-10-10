---
updatedAt: 2025-09-03T05:59:38.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate Image Using Lucid Origin

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "modelId": "7b592283-e8a7-4c5a-9ba6-d18c31f258b9",
  "contrast": 3.5,
  "prompt": "a portrait-style photograph featuring a fox with a slender build and delicate features sitting against a navy blue background that is smooth and untextured. The fox has soft, fluffy orange fur with a lighter patch on its chest and around its nose. Its ears are large and pointed, with a slight perkiness. The eyes are a bright, piercing yellow with a sharp, intelligent glint. The lighting is soft and warm, highlighting the texture of the fur.",
  "num_images": 4,
  "width": 1920,
  "height": 1080,
  "ultra": false,
  "styleUUID": "111dc692-d470-4eec-b791-3475abac4c46",
  "enhancePrompt": true
}
'

# Wait for a few seconds for images to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

# Create a generation of images

<!-- shell@1-18 -->

This command creates a generation of images using the Lucid Origin model.

To use this command, first replace <YOUR_API_KEY> with your API key. Then, run it in your terminal.

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- shell@20-25 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of URL links for downloading the images together with metadata.