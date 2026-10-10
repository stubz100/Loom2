---
updatedAt: 2026-02-18T02:58:24.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Guide to Get API Code

Explore visually, deploy instantly - turn your generations into production ready code

The Get API Code feature bridges the gap between experimenting in the Leonardo web app and implementing via the Production API. Once you've achieved the results you want in the web app, you can instantly export the exact configuration as ready-to-use code snippets.

## How It Works

After generating an image or video in the Leonardo web app, you can access the Get API Code option from the generation's menu. This opens a modal where you can select your preferred programming language and copy the code snippet to use in your application.
This feature is available to users with an active Production API account.

<Image align="center" width="500px" src="https://files.readme.io/d11908d3af4dc46e349b3c7cd31a6222adadbe4748290006e15e81ee825212a3-2._Get_API_Code.png" />

## Using Get API Code

Follow these steps to export your generation as API code:

1. **Generate your content in the web app**
   Create an image or video in the [generation page](https://app.leonardo.ai/image-generation). Choose model, and adjust all parameters and settings until you achieve your desired result.
2. **Access the generation menu**
   Once your generation is complete, click the three-dot menu (⋯) on the generation to open additional options.
3. **Select Get API Code**
   From the menu, choose *Get API Code*.
4. **Select your programming language**
   In the modal that opens, choose from available programming languages: cURL, Python, or Node.js.
5. **Copy the code snippet**
   Click the copy button to add the code snippet to your clipboard. The snippet includes all the parameters and settings from your web app generation, pre-configured with the correct API endpoint.
6. **Implement in your application**
   Paste the code into your project. Remember to replace **YOUR\_API\_KEY** with your actual Production API key.

> 📘 Note
>
> * Test the code snippet with a small number of generations first to ensure it works as expected.
> * The code snippet reflects the exact settings from your web app generation, but you can modify parameters as needed.
> * Review the specific model guide in our documentation for additional parameter options or further guidance on capabilities.

## When Get API Code Isn't Available

Not all models currently support code snippet generation. If you attempt to use *Get API Code* on an unsupported model, you'll see a message explaining that the feature isn't available for that specific model.

In these cases, visit the model's guide in our documentation for sample requests and required parameters. You can find guides for all models in the Image Generation, Video Generation or Legacy Generation sections in order to construct the API request manually for the model.