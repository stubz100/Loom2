---
updatedAt: 2026-07-28T08:33:32.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Sound Effects v2

This guide shows how to generate sound effects using the Sound Effects v2 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "sound-effects-v2",
    "public": false,
    "parameters": {
      "prompt": "Heavy wooden door creaking open in a large stone hall",
      "duration": 4,
      "prompt_influence": 0.7,
      "loop": false,
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

| Parameter         | Type      | Definition                                                                                                    |
| :---------------- | :-------- | :------------------------------------------------------------------------------------------------------------ |
| duration          | `number`  | Duration of the generated sound effect in seconds. Set to any whole number from `1` to `22`. Defaults to `2`. |
| loop              | `boolean` | Whether the generated sound effect loops. Defaults to `false`.                                                |
| model             | `string`  | Specifies the model used for generation. Set to `sound-effects-v2`.                                           |
| prompt            | `string`  | Text description of the sound effect to generate. Maximum of 9999 characters.                                 |
| prompt\_influence | `number`  | Controls how closely the output follows the prompt. Ranges from `0` to `1`. Defaults to `0.7`.                |
| public            | `boolean` | Controls whether the generated audio is public (true) or private (false).                                     |
| quantity          | `number`  | The number of outputs to generate. Set to `1`, `2`, `3`, or `4`. Defaults to `1`.                             |

<br />