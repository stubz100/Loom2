---
updatedAt: 2026-02-18T03:01:42.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Legacy FAQs

Answers to frequently asked questions when integrating to Leonardo.Ai via API

# Models

### What is the model ID of PhotoReal?

**PhotoReal v1** does not have a model ID.

To use PhotoReal on the Production API, you need to remove the modelId parameter and enable the photoReal flag.

For an example, check out the [Generate Images Using PhotoReal](https://docs.leonardo.ai/docs/generate-images-using-photoreal) sample recipe.

**PhotoReal v2** requires Leonardo Kino XL, Leonardo Diffusion XL or Leonardo Vision XL models. See [here](https://docs.leonardo.ai/docs/generate-images-using-photoreal#sample-request) for a sample request.

### Can I use my custom model with the Leonardo API?

Yes, you can use your own custom model with the Leonardo API.

### How do I find my custom model ID?

On the Leonard App, navigate to the [Finetune Models](https://app.leonardo.ai/finetuned-models). Click on the Your Models tab. Click on the model, then click on View More. This should reveal the Model ID of that particular custom model.

<Image align="center" width="600px" src="https://files.readme.io/2d861c343bcbe83b4b45115a37968c111b8102aa586d7a0cad963d921c9cd415-4.1_Fine_Tuned_Models_.png" />

# Generating Images

### How do I use Alchemy v2 on the API?

Alchemy V2 works with SDXL models like Leonardo Vision XL, Leonardo Diffusion XL, AlbedoBase XL and KinoXL. To use Alchemy v2, choose an SDXL model and simply set the alchemy parameter to true. This setup will use Alchemy v2.

### Why is my guidance scale setting not reflected?

The guidance scale is an advanced parameter and Leonardo advises to use a guidance scale of 7 in most cases.

There are some default behaviours and conditions applied when trying to control the guidance scale. The conditions and logic are as follows:

* If not set, guidance scale default is 7.
* If not using Alchemy, guidance scale is limited to 1-20.
* If using Alchemy but not using an SDXL model, guidance scale is limited to 2-30.
* If not using Alchemy and scheduler is set to LEONARDO, guidance scale is capped at 7.

### How do you set Prompt Magic V3 to RAW mode using the API?

To set Prompt Magic V3 to RAW mode, set`"highContrast": false`. This is similar to enabling RAW mode on the Leonardo app.

### How do you set Alchemy's Resonance using the API?

To set Alchemy's resonance, use the `guidance_scale `parameter. This controls the resonance setting on the UI.

### Why is the output image bigger than the height and width I specified?

The input resolution is not always equal to the output resolution. When you use Alchemy and high resolution, the output resolution could be bigger by 1.5x, 1.75x, 2x, etc. compared to the input resolution due to upscaling built in to this features. For example, when using Alchemy v2, the output dimension is 1.75 times bigger. When using Alchemy v1, the output is 1.5 times bigger. When using Alchemy v1 and high resolution, the output is twice the input.

To check, you can observe this in the Leonardo web app as the following image.

<Image align="center" width="400px" src="https://files.readme.io/11f7177d32d3ca870c54186d26c8c3c25a13c3f00057e724316df11612954c89-4.2_Output_image_bigger_than_specified.png" />

# Generating Motion

### Why am I seeing Service Error when generating SVD motion?

Although `Service Error`is a generic error message, in this scenario, the error is commonly due to incorrect IDs being used. Ensure that the ID is not the `generationId`from the [Create a Generation of Images API.](https://docs.leonardo.ai/reference/creategeneration), but rather the Image Id from [Get a Single Generation.](https://docs.leonardo.ai/reference/getgenerationbyid). The `generationId` needs to be passed to [Get a Single Generation.](https://docs.leonardo.ai/reference/getgenerationbyid) , and the returned image `Id` can then be used in the [Create SVD Motion Generation API](https://docs.leonardo.ai/reference/createsvdmotiongeneration).

# API Credits

### Why is the cost of generating images different using API credits vs Web Tokens?

Charges are calculated differently for API calls compared to generating using Web Tokens from the Web App, resulting in variations in costs. Additionally, API credits do not expire, whereas Subscription Tokens have a limited validity period.

### How do I top up my API plan with more API credits?

You can buy instant top up API credits via the Leonardo.Ai app. Navigate to [API Access ](https://app.leonardo.ai/api-access)on the left side menu, click on Production API tab, and click on the Top-up Credits button.

<Image align="center" width="600px" src="https://files.readme.io/e350b12d9f71ed9e38e40b7452323383a0cb673ab30778cf027fc2f6e2431cf8-4.3_API_top_up.png" />

### Do API Credits expire?

No, API Credits do not expire. However, note that you can only use your API credits when you have an active API Plan Subscription.

### I still have credits why can't I make anymore API calls?

Please ensure your API plan is active as you won't be able to access your credits without being on an API Plan.

### My API credit balance is negative, is that normal?

Yes, it's normal for API credits to go negative.\
​\
Blocking your usage once you run out of API credits is not a precise process. There are expected ways you could get to negative but our system won't let you get too far with a negative API credit balance.\
​\
Note that the negative API credits will be deducted from the next API credit top-up. To avoid running out of credits, [plan your usage](https://docs.leonardo.ai/docs/plan-with-the-pricing-calculator) or [set up auto top-ups](https://docs.leonardo.ai/docs/manage-usage-with-auto-top-up).

### Do I still get charged credits if my generation failed?

If you got charged credits but your generations failed via API, the credits will get refunded back into your account.

### How do I find the invoice for my API subscription plan?

We use Paddle.com for our payment system, please head over to <https://paddle.net/> and enter your email to locate your receipt. A copy of your invoice would also have been sent to your email automatically after payment.

# API Admin

### Where did the User API key go?

The User API key is now a deprecated feature and has been replaced by the Production API key. This key can be used for all API endpoints and can be generated here. Existing User API keys still work, but new ones need to be generated as Production API keys.