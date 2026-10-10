---
updatedAt: 2025-09-03T05:59:45.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate Images Using Leonardo Phoenix Model in Quality Mode

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "modelId": "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3",
  "contrast": 3.5,
  "prompt": "an orange cat standing on a blue basketball with the text PAWS",
  "num_images": 4,
  "width": 1472,
  "height": 832,
  "alchemy": true,
  "styleUUID": "111dc692-d470-4eec-b791-3475abac4c46",
  "enhancePrompt": false
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

This command creates a generation of images using the Leonardo Phoenix model.

To use this command, first replace <YOUR_API_KEY> with your API key. Then, run it in your terminal.

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- shell@21-26 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of URL links for downloading the images together with metadata.