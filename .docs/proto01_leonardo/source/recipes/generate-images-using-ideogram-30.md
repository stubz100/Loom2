---
updatedAt: 2026-01-23T02:07:26.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate Images Using Ideogram 3.0

```python Python
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
       "model": "ideogram-v3.0",
       "parameters": {
           "width": 1024,
           "height": 1024,
           "prompt": "A dynamically stylish green running shoe dominates the frame, with the text Leonardo, the text boldly emblazoned in white. Against a vivid blue backdrop, the shoe exudes modernity with a hint of motion blur, conveying speed and dynamism. Crisp lines and vibrant hues are subtly softened, capturing the essence of movement",
           "mode": "TURBO",
           "quantity": 2,
           "style_ids": [
               "111dc692-d470-4eec-b791-3475abac4c46"
           ]
       },
       "public": false
}
'

# Wait for a few seconds for images to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

# Create a generation of images

<!-- python@1-21 -->

This command creates a generation of images using the Ideogram model.

To use this command, first replace \<YOUR_API_KEY> with your API key. Then, run it in your terminal.

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- python@23-28 -->

To fetch your images, replace \<YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of URL links for downloading the images together with metadata.