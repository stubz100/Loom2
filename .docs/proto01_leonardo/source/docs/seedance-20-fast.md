---
updatedAt: 2026-07-04T08:58:14.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Seedance 2.0 Fast

This guide shows how to generate videos using the Seedance 2.0 Fast model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
--url https://cloud.leonardo.ai/api/rest/v2/generations \
--header 'accept: application/json' \
--header 'authorization: Bearer <YOUR_API_KEY>' \
--header 'content-type: application/json' \
--data '
{
  "model": "seedance-2.0-fast",
  "public": false,
  "parameters": {
    "prompt": "The koala plays with the cat",
    "quantity": 1,
    "guidances": {
      "start_frame": [
        {
          "image": {
            "id": "<YOUR_START_IMAGE_ID>",
            "type": "UPLOADED"
          }
        }
      ],
      "end_frame": [
        {
          "image": {
            "id": "<YOUR_END_IMAGE_ID>",
            "type": "UPLOADED"
          }
        }
      ]
    },
    "duration": 8,
    "motion_has_audio": true,
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

| Parameter                        | Type    | Definition                                                                                                                                                                                                      |
| -------------------------------- | ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| duration                         | integer | Length of the generated video in seconds. Valid values are `4`, `5`, `6`, `7`, `8`, `9`, `10`, `11`, `12`, `13`, `14`, `15`. Defaults to `8`.                                                                   |
| guidances.audio\_reference       | array   | Maximum 1 item. Optional audio reference used to guide the generation.                                                                                                                                          |
| guidances.end\_frame             | array   | Maximum 1 item. Each item includes an `image` object (`image.id` and `image.type`). Used as the end frame of the video.                                                                                         |
| guidances.image\_reference       | array   | Maximum 4 items. Each item includes `image` (object), `strength` (`LOW`, `MID`, or `HIGH`; defaults to `MID`), and an optional `order` (integer ≥ 0). Reference images that guide the video generation.         |
| guidances.start\_frame           | array   | Maximum 1 item. Each item includes an `image` object (`image.id` and `image.type`). Used as the start frame of the video.                                                                                       |
| guidances.video\_reference\_base | array   | Maximum 3 items. Optional base video reference used to guide the generation.                                                                                                                                    |
| height                           | integer | Sets the height of the output video in pixels. Defaults to `720`.                                                                                                                                               |
| mode                             | string  | Deprecated. Width and height are the canonical inputs for this model; this field is retained for backwards compatibility. Valid values are `RESOLUTION_480` and `RESOLUTION_720`. Defaults to `RESOLUTION_720`. |
| model                            | string  | Specifies the model used for generation. Must be `seedance-2.0-fast`.                                                                                                                                           |
| motion\_has\_audio               | boolean | Whether the generated video will include audio. Defaults to `true`.                                                                                                                                             |
| prompt                           | string  | Text description of the video content to generate. Maximum of 5000 characters.                                                                                                                                  |
| public                           | boolean | Controls whether the generated video is public (`true`) or private (`false`).                                                                                                                                   |
| quantity                         | integer | The number of outputs to generate. Must be `1`. Defaults to `1`.                                                                                                                                                |
| seed                             | number  | The seed value for generation. Valid range is `-1` to `4294967295`. Defaults to `-1` (random).                                                                                                                  |
| width                            | integer | Sets the width of the output video in pixels. Defaults to `1280`.                                                                                                                                               |

## Dimensions

Width and height are supplied as integer pixel values and are the canonical inputs for this model. The default output is `1280` x `720` (720p).

The deprecated `mode` field maps to two resolution tiers and is retained only for backwards compatibility:

| Mode            | Resolution     |
| --------------- | -------------- |
| RESOLUTION\_480 | 480p           |
| RESOLUTION\_720 | 720p (default) |

> Note: Unlike Seedance 1.0 Pro, the Seedance 2.0 Fast schema does not enumerate a fixed set of allowed width/height pairings. Set `width` and `height` directly in pixels.

<br />