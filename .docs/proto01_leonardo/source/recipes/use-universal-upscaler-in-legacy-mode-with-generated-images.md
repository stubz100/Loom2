---
updatedAt: 2025-09-03T05:59:44.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Use Universal Upscaler in Legacy Mode with Generated Images

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "height": 512,
  "prompt": "A galaxy over snowy mountains",
  "modelId": "aa77f04e-3eec-4034-9c07-d0f619684628",//Leonardo Kino XL model
  "width": 512,
  "alchemy": true,
  "photoReal": true,
  "photoRealVersion":"v2",
}
'

# Wait for a few seconds for images to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'


# Copy the image Id and add it to generatedImageId 

curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/variations/universal-upscaler \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'

{
  "upscalerStyle": "CINEMATIC",
  "creativityStrength": 8,
  "upscaleMultiplier": 2,
  "generatedImageId": "<YOUR_GENERATED_IMAGE_ID>",
}

# Get the variation by Id

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/variations/<YOUR_VARIATION_ID>  \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

# Create a generation of images

<!-- shell@1-15 -->

This command creates a generation of images with parameters to create using PhotoReal v2. 

To use this command, first replace <YOUR_API_KEY> with your API key. Then, run it in your terminal.

Notice that the model is set to a specific model ID corresponding to the Leonardo Kino XL model. You can use any platform model or your own custom model by setting modelId.

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- shell@18-23 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of URL links for downloading the images together with metadata. 

Take note of the image Id. 

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Upscale with Universal Upscaler

<!-- shell@26-38 -->

This example upscales the generated image using the Universal Upscaler. 

creativityStrength refers to how 'creative' the AI will be on the original image. The higher it is, the more variation will be applied. 

A higher upscaleMultiplier results in a larger and higher resolution image. The maximum megapixel size is 20MP.  

The response will contain a variation Id that you will need in the next step.

# Get images using variation ID

<!-- shell@40-45 -->

To fetch your Upscaled image, replace <YOUR_VARIATION_ID> in the URL with the id acquired from the previous step.

The response will contain a of URL for downloading the images together with metadata.