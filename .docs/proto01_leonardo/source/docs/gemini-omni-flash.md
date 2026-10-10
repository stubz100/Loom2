---
updatedAt: 2026-07-07T03:39:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Gemini Omni Flash

This guide shows how to generate videos using the Gemini Omni Flash model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "gemini-omni-flash",
    "public": false,
    "parameters": {
      "prompt": "The koala plays with the cat",
      "guidances": {
        "image_reference": [
          {
            "image": {
              "id": "<YOUR_IMAGE_ID>",
              "type": "UPLOADED"
            },
            "strength": "MID"
          }
        ]
      },
      "duration": 5,
      "quantity": 1,
      "width": 1280,
      "height": 720
    }
}
'
```

#

# API Request Endpoint, Headers, Parameters

## Endpoint

```curl
https://cloud.leonardo.ai/api/rest/v2/generations
```

## Headers

```curl
--header "accept: application/json" \
--header "authorization: Bearer <YOUR_API_KEY>" \
--header "content-type: application/json"
```

## Body Parameters

| Parameter                  | Type      | Definition                                                                                                                                                                                                                                                                              |
| :------------------------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                   | `number`  | Length of the generated video in seconds. Set to `3`, `4`, `5`, `6`, `7`, `8`, `9`, `10`. Defaults to `5`.                                                                                                                                                                              |
| guidances.image\_reference | `array`   | Maximum 5 items. References images to guide the video generation. Each item includes image.id, image.type (`INIT`, `GENERATION`, `UPLOADED`, `GENERATED`, or `VARIATION`), and strength (`LOW`, `MID`, or `HIGH`; defaults to `MID`). An optional order sets the ordering of guidances. |
| height                     | `number`  | Sets the height of the output video in pixels.                                                                                                                                                                                                                                          |
| model                      | `string`  | Specifies the model used for generation. Set to `gemini-omni-flash`.                                                                                                                                                                                                                    |
| prompt                     | `string`  | Text description of the video content to generate. Maximum of 2500 characters.                                                                                                                                                                                                          |
| public                     | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                                                                                                               |
| quantity                   | `number`  | The number of outputs to generate. Set to `1`. Defaults to `1`.                                                                                                                                                                                                                         |
| width                      | `number`  | Sets the width of the output video in pixels.                                                                                                                                                                                                                                           |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution | Aspect Ratio     | Pixel Values (Width x Height) |
| :--------- | :--------------- | :---------------------------- |
| 720p       | 16:9 (Landscape) | 1280x720                      |
|            | 9:16 (Portrait)  | 720x1280                      |

`width` and `height` must be set together using one of the combinations above, or omitted together.