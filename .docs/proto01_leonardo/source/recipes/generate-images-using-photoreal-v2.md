---
updatedAt: 2025-09-03T05:59:44.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate Images Using PhotoReal v2

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "height": 512,
  "prompt": "A fluffy happy dog",
  "modelId": "aa77f04e-3eec-4034-9c07-d0f619684628",//Leonardo Kino XL model
  "width": 512,
  "alchemy": true,
  "photoReal": true,
  "photoRealVersion":"v2",
  "presetStyle": "CINEMATIC"
}
'

# Wait for a few seconds for images to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

# Create a generation of images

<!-- shell@1-17 -->

This command creates a generation of images with PhotoReal v2 enabled.

To use this command, first replace <YOUR_API_KEY> with your API key. Then, run it in your terminal.

The command requires modelId specified as either Leonardo Kino XL, Leonardo Diffusion XL or Leonardo Vision XL.  

Alchemy is also required to use PhotoReal. 

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- shell@19-25 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of URL links for downloading the images together with metadata.

For production use cases, use the API's webhook callback feature to receive a message containing the output.