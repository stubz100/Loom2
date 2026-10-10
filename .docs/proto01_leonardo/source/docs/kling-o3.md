---
updatedAt: 2026-02-10T06:02:54.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Kling O3

This guide shows how to generate and edit videos using Kling O3 model via the Leonardo.AI REST API.

This guide shows how to generate and edit videos using **Kling O3** model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "kling-video-o-3",
    "public": false,
    "parameters": {
      "prompt": "The woman plays with the cat",
      "duration": 3,
      "width": 1920,
      "height": 1080,
      "mode": "RESOLUTION_1080",
      "motion_has_audio": true,
      "guidances": {
        "start_frame": [
          {
            "image": {
              "id": "<YOUR_START_IMAGE_ID>",
              "type": "UPLOADED"
            }
          }
        ]
      }
    }
}
'
```

# Recipe

<Recipe slug="edit-with-kling-o3-using-video-reference" title="Edit with Kling O3 using Video Reference" />

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

| Parameter                        | Type      | Definition                                                                                                                                                                                                                                                                            |
| :------------------------------- | :-------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| duration                         | `number`  | Length of the generated video. Set to `3`to `15`. Maximum of `10` seconds when specifying a video reference.                                                                                                                                                                          |
| guidances.end\_frame             | `array`   | Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`). Only available when `start_frame` is provided. Only available when NO `image_reference` is provided.                                                                                          |
| guidances.image\_reference       | `array`   | Array of up to 7 reference images used to guide the visual style or content of the generation, or up to 4 when specifying a video reference. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`). Only available when NO `start_frame` or `end_frame` is provided. |
| guidances.start\_frame           | `array`   | Maximum 1 item. Each item includes image.id and image.type (`GENERATED` or `UPLOADED`). Only available when NO `image_reference` is provided.                                                                                                                                         |
| guidances.video\_reference\_base | `array`   | Specify the video to edit. Maximum 1 item. Each item includes video.id and video.type (`GENERATED` only). Can be used with `image_reference`. Only available when NO `start_frame` or `end_frame` is provided.                                                                        |
| height                           | `number`  | Sets the height of the video in pixels.                                                                                                                                                                                                                                               |
| mode                             | `string`  | Quality modes. Specify `RESOLUTION_720` for Standard or  `RESOLUTION_1080` for Pro. Default is `RESOLUTION_1080`.                                                                                                                                                                     |
| model                            | `string`  | Specifies the model used for generation. Set to `kling-video-o-3`.                                                                                                                                                                                                                    |
| motion\_has\_audio               | `boolean` | Controls whether to generate audio (`true`) or not (`false`). Audio is not kept when editing videos specified as video reference.                                                                                                                                                     |
| prompt                           | `string`  | Text description of the video content to generate. Maximum of 1500 characters.                                                                                                                                                                                                        |
| public                           | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                                                                                                             |
| width                            | `number`  | Sets the width of the video in pixels.                                                                                                                                                                                                                                                |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution | Aspect Ratio | Pixel Values (Width x Height) |
| :--------- | :----------- | :---------------------------- |
| 720p       | 16:9         | 1280x720                      |
|            | 1:1          | 960x960                       |
|            | 9:16         | 720x1280                      |
| 1080p      | 16:9         | 1920x1080                     |
|            | 1:1          | 1440x1440                     |
|            | 9:16         | 1080x1920                     |

**Note:** When `width` and `height`are not specified, and `guidances.start_frame` is specified, the generation will base the dimensions on the `guidances.start_frame` image.