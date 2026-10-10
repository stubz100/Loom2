---
updatedAt: 2025-09-03T05:59:39.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate Images Using PhotoReal

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "height": 512,
  "prompt": "A cat staring at a window",
  "width": 512,
  "alchemy": true,
  "photoReal": true,
  "photoRealStrength": 0.5,
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

<!-- shell@1-16 -->

This command creates a generation of images with PhotoReal enabled.

To use this command, first replace <YOUR_API_KEY> with your API key. Then, run it in your terminal.

Notice that the command does not specify modelID and has Alchemy enabled which are required for using PhotoReal.

The style is also set to Cinematic.

The depth of field (photoRealStrength) is set to 0.5 which corresponds to medium. Other options are 0.45 for high, and 0.55 for low depth of field.

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- shell@20-23 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of URL links for downloading the images together with metadata.