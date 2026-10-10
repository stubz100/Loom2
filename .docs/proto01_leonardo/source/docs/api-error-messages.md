---
updatedAt: 2026-01-28T22:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# API Error Messages

Debug common issues encountered when integrating to Leonardo.Ai via API

If you experience issues integrating your application via API, this list helps you troubleshoot. If you continue to have trouble, contact [Leonardo.Ai support](https://docs.leonardo.ai/docs/need-more-support) for further assistance.

### Invalid response from authorization hook

```
{  
  "error": "Invalid response from authorization hook",  
  "path": "$",  
  "code": "unexpected"  
}
```

Check if your API key follows a valid [UUID format.](https://en.wikipedia.org/wiki/Universally_unique_identifier)

Check if your API key is correct.

Check if you are setting the API key correctly. It should be added to the request header as `authorization: Bearer XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX.`

For example, when using the curl command:

```
curl --request POST \

     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX' \
     --header 'content-type: application/json' \
     --data '
{
  "height": 512,
  "modelId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
  "prompt": "An oil painting of a cat",
  "width": 512
}
'
```

### Authentication hook unauthorized this request

```
{
  "error": "Authentication hook unauthorized this request",
  "path": "$",
  "code": "access-denied"
}

```

Similar to Invalid response from authorization hook, check if you are setting the API key correctly. It should be added to the request header as` authorization: Bearer XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX.`

### Invalid file extension

```
{  
  "error": "invalid file extension",  
  "path": "$",  
  "code": "unexpected"  
}
```

The `extension` parameter in [Upload Init Image API](https://docs.leonardo.ai/reference/uploadinitimage) is the file extension of the image you will upload. Examples of file extensions are` png`, `jpg`, `jpeg`, and `webp` . The extension parameter does not accept filenames or the image data.

The [Upload Init Image AP](https://docs.leonardo.ai/reference/uploadinitimage)I returns a presigned URL for uploading the image. Detailed instructions for using the returned presigned URL are available in the guide: [How to upload an image using a presigned URL](https://docs.leonardo.ai/docs/how-to-upload-an-image-using-a-presigned-url).

### Expected a boolean for type Boolean but found a string

```
{  
  "error": "expected a boolean for type 'Boolean', but found a string",  
  "path": "$.selectionSet.sdGenerationJob.args.arg1.photoReal",  
  "code": "validation-failed"  
}
```

Check if your code is converting your input into string instead of a Boolean value. The accepted values are `true` or `false`. Setting `"true"` or `"false"` in quotations may be interpreted as string.

### Unexpected variable

```
{  
  "error": "Unexpected variable sd_Version",  
  "path": "$",  
  "code": "bad-request"  
}
```

Check if you are specifying the correct body parameter. Body parameters are case-sensitive. For example, `sd_version` is the correct parameter so specifying `sd_Version` will throw the unexpected variable error.

### 204 (No Content) when uploading an image

When [uploading an image via a presigned URL](https://docs.leonardo.ai/docs/how-to-upload-an-image-using-a-presigned-url), 204 is the expected success response code and there will be no content returned. The image ID will not be returned here. Instead, the image ID has already been returned in the previous step of calling the [Upload Init Image API.](https://docs.leonardo.ai/reference/uploadinitimage)

For example, the image ID is under uploadInitImage.id below:

```
{  
  "uploadInitImage": {  
    "id": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",  
    "fields": …,  
    "key": …,  
    "url": …  
  }  
}
```

### 400 Bad Request: Too many images

When [creating a generation of images](https://docs.leonardo.ai/reference/creategeneration), specify a lower `num_images`because you are requesting too many images in one request. Depending on the size and setting of your image generation request, there will be a maximum supported number of images per one request. If you need more images, you need to make a separate image generation request.

### 403 Forbidden error when uploading an image

When [uploading an image via a presigned URL](https://docs.leonardo.ai/docs/how-to-upload-an-image-using-a-presigned-url), remove authentication-related headers like your API key because it is not necessary when using the presigned URL.

### 403 Forbidden: content moderation filter

Sample 1:

```
{
  "error": "Your prompt appears to contain inappropriate content, please be mindful of our Terms of Service. You may modify your prompt and try again.",
  "path": "$",
  "code": "unexpected"
}
```

Sample 2:

```
{
  "error": "content moderation filter: naked",
  "path": "$",
  "code": "unexpected"
}
```

This error means your generation request may generate an image that is outside of Leonardo's Terms of Service. We recommend avoiding prompts that may lead to depictions of pornography, violence, etc. as listed in the Limitations of Use in our [Terms of Service](https://leonardo.ai/terms-of-service/).

### Couldn't access image

```
{  
  "error": "couldn't access image",  
  "path": "$",  
  "code": "unexpected"  
}
```

When using variations like the[ Create Upscale API](https://docs.leonardo.ai/reference/createvariationupscale) and [Create Unzoom API,](https://docs.leonardo.ai/reference/createvariationunzoom) the expected image ID is the ID of an image generated on Leonardo.Ai. This image ID is returned by the [Get a Single Generation API.](https://docs.leonardo.ai/reference/getgenerationbyid)

For example, the image ID is under `generations_by_pk.generated_images[0].id `below:

```
{  
  "generations_by_pk": {  
    "generated_images": \[  
      {  
        "url": …,  
        "nsfw": …,  
        "id": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",  
        "likeCount": …,  
        "generated_image_variation_generics": \[]  
      },  
    ],  
   …  
  }  
}
```

Currently, we don’t support using variations on images uploaded via the [Upload Init Image API.](https://docs.leonardo.ai/reference/uploadinitimage)

### Failed to find init variation

```
{  
  "error": "failed to find init variation",  
  "path": "$",  
  "code": "unexpected"  
}
```

Similar to **Couldn't access image**, the expected image ID is the ID of an image generated on Leonardo.Ai. This image ID is returned by the [Get a Single Generation API.](https://docs.leonardo.ai/reference/getgenerationbyid)

### Invalid init image id

```
{  
  "error": "invalid init image id",  
  "path": "$",  
  "code": "unexpected"  
}
```

Check if your init image ID follows a valid [UUID format.](https://en.wikipedia.org/wiki/Universally_unique_identifier)

The`init_image_id`parameter accepts the image ID returned by the[ Upload Init Image API. ](https://docs.leonardo.ai/reference/uploadinitimage)To use an image generated in Leonardo.Ai as init image, specify the image ID in the `init_generation_image_id` parameter instead.

### 200 Success but image URL array is empty

Check if the response body contains `"status": "COMPLETE"`. The endpoint returns an attribute `generations_by_pk.status`. Successfully completed image generation would have a status of COMPLETE.

The reason is that [Get a Single Generation API endpoint ](https://docs.leonardo.ai/reference/getgenerationbyid)is returning 200 success response with an empty `generations_by_pk.generated_images[].` Image URLs are not returned.\
​\
Image generation is not instantaneous so be sure you are not getting the images immediately after sending a generate images request. The best practice is to specify a [webhook callback](https://docs.leonardo.ai/docs/guide-to-the-webhook-callback-feature) when creating the API key to receive a message containing the URL of generated images.

### Key Creation Error Occurred

**Symptom**: Generating a Production API key while specifying a webhook callback results to a UI error saying "Key Creation Error Occurred".

Check if you are using https for the webhook URL and not http. You can find the following console error "WebhookCallbackUrl is not a valid url" if you use http:

```
{  
    "errors": [  
        {  
            "message": "WebhookCallbackUrl is not a valid url (must be https://)",  
            "extensions": {  
                "path": "$",  
                "code": "unexpected"  
            }  
        }  
    ]  
}
```

### Failed to find init variation

```
{  
  "error": "failed to find init variation",  
  "path": "$",  
  "code": "unexpected"  
}
```

When using variation API endpoints like [unzoom](https://docs.leonardo.ai/reference/createvariationunzoom) and [no background,](https://docs.leonardo.ai/reference/createvariationnobg) setting the parameter isVariation to true means that the image ID you are supplying is a product of a previous variation.\
​\
For example, you used the variation API endpoint [upscale](https://docs.leonardo.ai/reference/createvariationupscale) and got an image ID. If you wish to use [no background](https://docs.leonardo.ai/reference/createvariationnobg) on that ID, you need to set `isVariation` to `true.`

If the ID is not from a previous variation, set `isVariation` to `false` or don't specify it.

### Service Error

```
{
"error": "Service Error",
"path": "$",
"code": "unexpected"
}
```

This is a generic error message from Leonardo.Ai. Reach out to [support](https://dash.readme.com/project/leonardoai/v1.0/docs/need-more-support) for further troubleshooting. If this is occurring when creating Motion SVD generations, ensure you are using the image Id from [Get a single Generation ](https://docs.leonardo.ai/reference/getgenerationbyid)instead of generation Id from [Create a generation of Images.](https://docs.leonardo.ai/reference/creategeneration)

### Invalid Dimensions

```
{
  "error": "invalid dimensions",
  "path": "$",
  "code": "unexpected"
}
```

An error commonly seen when applying Alchemy. Ensure that your height and width dimensions are within 32 to 1024 and are in multiples of 8. Images gone through the Alchemy pipeline will end up larger than the initial input dimensions.

### Expecting a value for non-nullable variable: "prompt"

```
{
    "error": "expecting a value for non-nullable variable: \"prompt\"",
    "path": "$",
    "code": "validation-failed"
}
```

This error is a generic error that appears when the API body is incorrectly formatted. This message shows because 'prompt' is the only required field for the [Create Generation of Images](https://docs.leonardo.ai/reference/creategeneration) endpoint. Check that your API body is correctly formatted.

### Invalid prompt, maximum length of 1500 characters exceeded.

```
{
  "error": "Invalid prompt, maximum length of 1500 characters exceeded.",
  "path": "$",
  "code": "unexpected"
}
```

This error is usually seen when the prompt exceeds 1,500 characters. Try shortening your prompt to stay within the limit.

### Prompt is too long, please keep it under 200 characters

```
{
  "error": "Prompt is too long, please keep it under 200 characters",
  "path": "$",
  "code": "unexpected"
}
```

This error is usually seen when using the Improve Prompt endpoint. Make sure your prompt is under 200 characters.

### Model is not supported within the Production API

```
{
  "error": "<MODEL_ID> is not supported within the Production API. Please try again with a different model ID.",
  "path": "$",
  "code": "unexpected"
}
```

This error is returned when the model requested is not supported within the Production API.