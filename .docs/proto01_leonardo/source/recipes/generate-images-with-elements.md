---
updatedAt: 2025-09-03T05:59:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate Images with Elements

```shell Shell
curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/elements \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
     
# Note the element's akUUID, base model, and weight range. 

curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "height": 512,
  "prompt": "A dog in space",
  "width": 512,
  "elements": [
    {
      "akUUID": "01b6184e-3905-4dc7-9ec6-4f09982536d5",
      "weight": 1.2
    }
  ],
  "sd_version": "v1_5"
}
'
# Wait for a few seconds for images to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

# List all Elements and pick the chosen element

<!-- shell@1-6 -->

This command lists out all the current Elements (LoRAs) on Leonardo AI.

To use this command, first replace <YOUR_API_KEY> with your API key. Then, run it in your terminal.

The response will contain an array of multiple elements. Choose the specified Element of choice and use the "akUUID" attribute for the next step.

Keep in mind the "baseModel" settings as some are not compatible with certain SD models. Take note of the weight range specified in the Element attributes for the next step.

# Create a generation of images with Elements

<!-- shell@8-26 -->

This example creates a generation of images using an example Element with a weight of 1.2 as the basic parameters.

Note the sd_version is specified as v1_5 as per the specifications in the List Elements call in the previous step. Do not enter a modelId in this step. 

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- shell@27-33 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of URL links for downloading the images together with metadata.

For production use cases, use the API's webhook callback feature to receive a message containing the output.