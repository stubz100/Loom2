---
updatedAt: 2025-09-03T05:59:39.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate your First Images

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "height": 512,
  "modelId": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3",
  "prompt": "An oil painting of a cat",
  "width": 512
}
'

# Wait for a few seconds for images to be generated.

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

```node Node
const axios = require("axios");

const API_KEY = "<YOUR_API_KEY>";
const AUTHORIZATION = `Bearer ${API_KEY}`;

const HEADERS = {
  accept: "application/json",
  "content-type": "application/json",
  authorization: AUTHORIZATION,
};

async function generateImage() {
  try {
    // Step 1: Send a request to generate an image
    let url = "https://cloud.leonardo.ai/api/rest/v1/generations";
    let payload = {
      height: 512,
      modelId: "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3", // Model ID for the chosen model
      prompt: "An oil painting of a cat",
      width: 512,
    };

    let response = await axios.post(url, payload, { headers: HEADERS });

    console.log("Generate an image request:", response.status);

    if (response.status !== 200) {
      throw new Error("Failed to create image generation request");
    }

    let generationId = response.data.sdGenerationJob.generationId;
    console.log("Generation ID:", generationId);

    // Step 2: Wait before fetching the generated image
    url = `https://cloud.leonardo.ai/api/rest/v1/generations/${generationId}`;

    console.log("Waiting for image generation to complete...");
    await new Promise((resolve) => setTimeout(resolve, 20000)); // Wait 20 seconds

    response = await axios.get(url, { headers: HEADERS });

    console.log("Get generated image response:", response.status);

    if (response.status !== 200) {
      throw new Error("Failed to fetch generated image details");
    }

    console.log("Generated Image Details:", response.data);

  } catch (error) {
    console.error("Error:", error.response ? error.response.data : error.message);
  }
}

// Run the function
generateImage();
```

# Create a generation of images

<!-- shell@1-13 -->
<!-- node@12-32 -->

This command creates a generation of images with minimal parameters.

To use this command, first replace <YOUR_API_KEY> with your API key. Then, run it in your terminal.

Notice that the model is set to a specific model ID corresponding to the Leonardo Creative model. You can use any platform model or your own custom model by setting modelId.

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- shell@15-20 -->
<!-- node@34-46 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of URL links for downloading the images together with metadata.