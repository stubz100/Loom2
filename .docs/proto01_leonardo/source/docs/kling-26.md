---
updatedAt: 2026-01-23T05:09:07.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Kling 2.6

This guide shows how to generate images using Kling 2.6 models via the Leonardo.AI REST API.

This guide shows how to generate images using **Kling 2.6** models via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "kling-2.6",
    "public": false,
    "parameters": {
      "prompt": "The woman plays with the cat",
      "guidances": {
        "start_frame": [
          {
            "image": {
              "id": "<YOUR_START_IMAGE_ID>",
              "type": "GENERATED"
            }
          }
        ]
      },
      "duration": 5,
      "width": 1080,
      "height": 1920
    }
}
'
```

# Recipe

<Recipe slug="generate-with-kling-26-using-start-frames" title="Generate with Kling 2.6 Using Start Frames" />

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

| Parameter              | Type      | Definition                                                                              |
| :--------------------- | :-------- | :-------------------------------------------------------------------------------------- |
| duration               | `number`  | Length of the generated video. Set to `5` or `10`.                                      |
| guidances.start\_frame | `array`   | Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`). |
| height                 | `number`  | Sets the height of the output video in pixels.                                          |
| model                  | `string`  | Specifies the model used for generation. Set to `kling-2.6`.                            |
| prompt                 | `string`  | Text description of the video content to generate. Maximum of 1500 characters.          |
| public                 | `boolean` | Controls whether the generated video is public (true) or private (false).               |
| width                  | `number`  | Sets the width of the output video in pixels.                                           |

## Height and Width Combinations

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Aspect Ratio     | Width | Height |
| :--------------- | :---- | :----- |
| 16:9 (Landscape) | 1920  | 1080   |
| 1:1 (Square)     | 1440  | 1440   |
| 9:16 (Portrait)  | 1080  | 1920   |

<br />