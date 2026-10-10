---
updatedAt: 2025-09-03T05:59:46.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate Images Using Flux

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "modelId": "b2614463-296c-462a-9586-aafdb8f00e36",
  "contrast": 3.5,
  "prompt": "an orange cat playing with a tennis ball with the text FLUX",
  "num_images": 4,
  "width": 1472,
  "height": 832,
  "ultra": true,
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

<!-- shell@1-19 -->

This command creates a generation of images using the Flux Dev model.

To use this command, first replace <YOUR_API_KEY> with your API key. Then, run it in your terminal.

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- shell@21-26 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of URL links for downloading the images together with metadata.