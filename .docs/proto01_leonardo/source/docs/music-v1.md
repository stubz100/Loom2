---
updatedAt: 2026-07-27T06:54:44.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Music v1

This guide shows how to generate music using the Music v1 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "music-v1",
    "public": false,
    "parameters": {
      "prompt": "An upbeat synthwave track with a driving bassline, punchy drums and dreamy pads",
      "duration_minutes": 2,
      "force_instrumental": true,
      "quantity": 1
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

| Parameter           | Type      | Definition                                                                                                                      |
| :------------------ | :-------- | :------------------------------------------------------------------------------------------------------------------------------ |
| duration\_minutes   | `number`  | Duration of the generated track in whole minutes. Set to `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, or `10`. Defaults to `1`. |
| force\_instrumental | `boolean` | When true, guarantees an instrumental-only output (no vocals). Defaults to `false`.                                             |
| model               | `string`  | Specifies the model used for generation. Set to `music-v1`.                                                                     |
| prompt              | `string`  | Text description of the music to generate. Maximum of 9999 characters.                                                          |
| public              | `boolean` | Controls whether the generated audio is public (true) or private (false).                                                       |
| quantity            | `number`  | The number of outputs to generate. Set to `1`, `2`, `3`, or `4`. Defaults to `1`.                                               |

<br />