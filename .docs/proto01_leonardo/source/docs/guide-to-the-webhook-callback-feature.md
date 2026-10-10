---
updatedAt: 2026-01-21T04:38:54.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Guide to the Webhook Callback Feature

Generating images will take a few seconds to complete. Instead of polling the [Get a Single Generation API endpoint](https://docs.leonardo.ai/reference/getgenerationbyid), it's more efficient to receive a message containing the links to your images and other metadata. To receive a message, you need to leverage the webhook callback feature.

# Setting the Webhook Callback

When creating a production API key, you have the option to fill in your webhook callback URL and webhook callback API key.

> 📘 Note
>
> * The webhook callback URL and webhook callback API key are not required for creating an API key.
> * The webhook callback URL field requires HTTPS.
> * The webhook callback API key will be used for authenticating to your webhook callback. It will be added to the header of the request as`authorization: Bearer $yourWebhookCallbackApiKey`.
> * To update your webhook callback URL and webhook callback API key, you need to create a new production API key with the new webhook details, then delete the old one after switching to the new API key.

# Examining Leonardo's Request to your Webhook

Many users find it useful to first study Leonardo's requests to their webhook using online tools like [Webhook.site](https://webhook.site/). Using such tools, you can analyse:

* Which host and where in the world will the request come from so you can allow those requests?
* What headers is Leonardo sending so you can make sure that your web servers, firewall, security tool, etc. do not block the requests?
* Is your webhook callback API key being passed correctly?

<Image align="center" alt="Sample screenshot for an online tool (Webhook.site) for examining HTTP requests." border={false} caption="Sample screenshot for an online tool (Webhook.site) for examining HTTP requests." src="https://files.readme.io/ef29782-Screenshot_2023-11-09_at_11.53.49.png" />

> 🚧 Not receiving messages in your webhook from Leonardo?
>
> * Note that the webhook callback API key will be added to the header of the request as `authorization: Bearer $yourWebhookCallbackApiKey`. Please make sure that your system expects that header.
> * Please check your system for anything that disallow traffic by IP address, location, headers, etc.
> * Please check if your SSL Certificate is configured correctly. For example, run `openssl s_client -showcerts -connect YOUR_DOMAIN:443 -servername YOUR_DOMAIN` to check if your server's certificate and intermediate certificates are properly set.

# Example Request to your Webhook

Below is a sample request made by Leonardo to a webhook callback.

```
curl -X 'POST' \
 'https://webhook.site/cc21af5f-4caa-498e-8f26-20c664680b73' \
 -H 'connection: close' \
 -H 'host: webhook.site' \
 -H 'accept-encoding: gzip, compress, deflate, br' \
 -H 'content-length: 3166' \
 -H 'user-agent: axios/1.4.0' \
 -H 'authorization: Bearer abcd' \
 -H 'content-type: application/json' \
 -H 'accept: application/json, text/plain, */*' \
 -d '{
    "type": "image_generation.complete",
    "object": "generation",
    "timestamp": 1699490546932,
    "api_version": "v1",
    "data": {
        "object": {
            "id": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            "createdAt": "2023-11-09T00:42:22.707Z",
            "updatedAt": "2023-11-09T00:42:26.740Z",
            "userId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            "public": false,
            "flagged": false,
            "nsfw": false,
            "status": "COMPLETE",
            "coreModel": "SD",
            "guidanceScale": 7,
            "imageHeight": 512,
            "imageWidth": 512,
            "inferenceSteps": 30,
            "initGeneratedImageId": null,
            "initImageId": null,
            "initStrength": null,
            "initType": null,
            "initUpscaledImageId": null,
            "modelId": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3",
            "negativePrompt": "",
            "prompt": "An oil painting of a cat",
            "quantity": 1,
            "sdVersion": "v2",
            "tiling": false,
            "imageAspectRatio": null,
            "tokenCost": 0,
            "negativeStylePrompt": "",
            "seed": "905778432",
            "scheduler": "EULER_DISCRETE",
            "presetStyle": null,
            "promptMagic": false,
            "canvasInitImageId": null,
            "canvasMaskImageId": null,
            "canvasRequest": false,
            "api": true,
            "poseImage2Image": false,
            "imagePromptStrength": null,
            "category": null,
            "poseImage2ImageType": null,
            "highContrast": false,
            "apiDollarCost": "9",
            "poseImage2ImageWeight": null,
            "alchemy": null,
            "contrastRatio": null,
            "highResolution": null,
            "expandedDomain": null,
            "promptMagicVersion": null,
            "unzoom": null,
            "unzoomAmount": null,
            "apiKeyId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
            "photoReal": false,
            "promptMagicStrength": null,
            "photoRealStrength": null,
            "imageToImage": false,
            "controlnetsUsed": false,
            "model": {
                "id": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3",
                "createdAt": "2023-01-06T01:02:38.315Z",
                "updatedAt": "2023-03-01T11:45:06.428Z",
                "name": "Leonardo Creative",
                "description": "An alternative finetune of SD 2.1 that brings a little more creative interpretation to the mix.",
                "public": true,
                "userId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                "flagged": false,
                "nsfw": false,
                "official": true,
                "status": "COMPLETE",
                "classPrompt": null,
                "coreModel": "SD",
                "initDatasetId": null,
                "instancePrompt": null,
                "sdVersion": "v2",
                "trainingEpoch": null,
                "trainingSteps": null,
                "tokenCost": null,
                "batchSize": 4,
                "learningRate": null,
                "type": "GENERAL",
                "modelHeight": 768,
                "modelWidth": 768,
                "leonardoInstancePrompt": null,
                "trainingStrength": "MEDIUM",
                "featured": false,
                "featuredImageId": null,
                "featuredPosition": 4,
                "api": false,
                "favouriteCount": 0,
                "imageCount": 2416039,
                "enhancedModeration": false,
                "apiDollarCost": null,
                "apiKeyId": null,
                "modelLRN": null
            },
            "images": [
                {
                    "id": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                    "createdAt": "2023-11-09T00:42:26.733Z",
                    "updatedAt": "2023-11-09T00:42:26.733Z",
                    "userId": "ef8b8386-94f7-48d1-b10e-e87fd4dee6e6",
                    "url": "https://cdn.leonardo.ai/users/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX/generations/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX/Leonardo_Creative_An_oil_painting_of_a_cat_0.jpg",
                    "generationId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                    "nobgId": null,
                    "nsfw": false,
                    "likeCount": 0,
                    "trendingScore": 0,
                    "public": false
                }
            ],
            "apiKey": {
                "id": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                "createdAt": "2023-11-07T00:11:07.274Z",
                "userId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                "key": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                "lastUsed": "2023-11-07T00:11:07.274Z",
                "name": "webhook with key",
                "type": "PRODUCTION",
                "webhookCallbackUrl": "https://webhook.site/cc21af5f-4caa-498e-8f26-20c664680b73",
                "webhookCallbackApiKey": "abcd"
            }
        }
    }
}
'
```

<br />

# IP Ranges Used for Leonardo Requests

The requests to your webhook will come from the following IP addresses:

```
35.173.108.170
34.239.69.60
52.73.75.186
3.229.99.26
44.218.0.197
174.129.230.221
```

Be sure to add them to your allowlist to ensure that Leonardo.Ai can make a request to your webhook.