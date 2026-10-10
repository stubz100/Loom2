---
updatedAt: 2026-09-02T04:58:25.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Motion 2.0 Fast

This guide shows how to generate videos using the Motion 2.0 Fast model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "motion_2.0-fast",
    "public": false,
    "parameters": {
      "prompt": "A koala and a cat playing together in a sunlit meadow",
      "guidances": {
        "start_frame": [
          {
            "image": {
              "id": "<YOUR_START_IMAGE_ID>",
              "type": "UPLOADED"
            }
          }
        ]
      },
      "quantity": 1,
      "prompt_enhance": "OFF",
      "frame_interpolation": true,
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

| Parameter              | Type      | Definition                                                                                                                                                                                           |
| :--------------------- | :-------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| controls               | `array`   | An array of Motion Control items (same format, but are defined separately from Motion Elements). Maximum 1 item. Each item includes `akUUID` (required) and `weight` (`-2` to `2`, defaults to `1`). |
| elements               | `array`   | An array of Motion Elements (same format, but are defined separately from Motion Control). Each item includes `akUUID` (required) and `weight` (`-2` to `2`, defaults to `1`). Defaults to `[]`.     |
| frame\_interpolation   | `boolean` | Whether the video generation will smoothly blend frames. Defaults to `true`.                                                                                                                         |
| guidances.start\_frame | `array`   | Creative reinterpretation of vibe or structure from a reference image. Maximum 1 item. Each item includes image.id and image.type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`).        |
| height                 | `number`  | Sets the height of the output video in pixels.                                                                                                                                                       |
| mode                   | `string`  | Deprecated. Width and height are the canonical inputs for this model. Retained for backwards compatibility. Valid values are `RESOLUTION_480` and `RESOLUTION_720`. Defaults to `RESOLUTION_480`.    |
| model                  | `string`  | Specifies the model used for generation. Set to `motion_2.0-fast`.                                                                                                                                   |
| negative\_prompt       | `string`  | The negative prompt to use for the generation. Maximum of 1000 characters.                                                                                                                           |
| prompt                 | `string`  | Text description of the video content to generate. Maximum of 9999 characters.                                                                                                                       |
| prompt\_enhance        | `string`  | Enables or disables prompt enhancement. Valid values are `AUTO`, `ON`, and `OFF`. Defaults to `AUTO`.                                                                                                |
| public                 | `boolean` | Controls whether the generated video is public (true) or private (false).                                                                                                                            |
| quantity               | `number`  | The number of outputs to generate. Set to `1`. Defaults to `1`.                                                                                                                                      |
| seed                   | `number`  | The seed value for video generation. Set to a value between `0` and `4294967295`.                                                                                                                    |
| start\_frame           | `object`  | Deprecated. The start frame init\_image to start a generation with. Includes id and type (`UPLOADED`, `GENERATED`, `VARIATION`, `URL`, or `BASE64`). Use `guidances.start_frame` instead.            |
| style\_ids             | `array`   | An array of zero or more style UUIDs for video models (vibe, lighting, color). Defaults to `[]`.                                                                                                     |
| width                  | `number`  | Sets the width of the output video in pixels.                                                                                                                                                        |

## Dimensions

The API accepts `width` and `height` parameters in the following aspect ratio combinations:

| Resolution | Aspect Ratio            | Pixel Values (Width x Height) |
| :--------- | :---------------------- | :---------------------------- |
| 480p       | 16:9 (Landscape)        | 832x480                       |
|            | 4:5                     | 576x720                       |
|            | 2:3                     | 512x768                       |
|            | 9:16 (Portrait)         | 480x832                       |
| 720p       | 16:9 (Landscape)        | 1280x720                      |
|            | 9:16 (Portrait)         | 720x1280                      |
| Auto       | Determined by the model | 0x0                           |

Both `width` and `height` must be supplied together, or omitted together.