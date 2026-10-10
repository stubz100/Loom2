---
updatedAt: 2026-07-28T08:34:21.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Dialogue v3

This guide shows how to generate spoken dialogue using the Dialogue v3 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "dialogue-v3",
    "public": false,
    "parameters": {
      "prompt": "Welcome back, traveller. The city gates close at sundown, so lets not waste any time.",
      "voice_id": "JBFqnCBsd6RMkjVDRZzb",
      "language_code": "en",
      "prompt_influence": 0.5,
      "quantity": 1
    }
}
'
```

# Recipe

<Recipe slug="generate-dialogue-with-dialogue-v3" title="Generate Dialogue with Dialogue v3" />

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

| Parameter         | Type      | Definition                                                                                                        |
| :---------------- | :-------- | :---------------------------------------------------------------------------------------------------------------- |
| language\_code    | `string`  | Language of the generated speech as an ISO 639-1 code (e.g. `en`). Defaults to `en`.                              |
| model             | `string`  | Specifies the model used for generation. Set to `dialogue-v3`.                                                    |
| prompt            | `string`  | The dialogue text to generate as speech. Maximum of 5000 characters.                                              |
| prompt\_influence | `number`  | Controls how closely the output follows the prompt. Ranges from `0` to `1`. Defaults to `0.5`.                    |
| public            | `boolean` | Controls whether the generated audio is public (true) or private (false).                                         |
| quantity          | `number`  | The number of outputs to generate. Set to `1`, `2`, `3`, or `4`. Defaults to `1`.                                 |
| voice\_id         | `string`  | ID of the preset voice used for speech. Defaults to `JBFqnCBsd6RMkjVDRZzb` (George). See List of Voice IDs below. |

## List of Voice IDs

The API accepts the following `voice_id` values:

| Voice   | Voice ID               |
| :------ | :--------------------- |
| Adam    | `pNInz6obpgDQGcFmaJgB` |
| Alice   | `Xb7hH8MSUJpSbSDYk0k2` |
| Bella   | `hpp4J3VqNfWAUOO0d1Us` |
| Bill    | `pqHfZKP75CvOlQylNhV4` |
| Brian   | `nPczCjzI2devNBz1zQrb` |
| Callum  | `N2lVS1w4EtoT3dr4eOWO` |
| Charlie | `IKne3meq5aSn9XLyUdCD` |
| Chris   | `iP95p4xoKVk53GoZ742B` |
| Daniel  | `onwK4e9ZLuTAKqWW03F9` |
| Eric    | `cjVigY5qzO86Huf0OWal` |
| George  | `JBFqnCBsd6RMkjVDRZzb` |
| Harry   | `SOYHLrjzK2X1ezoPC6cr` |
| Jessica | `cgSgspJ2msm6clMCkdW9` |
| Laura   | `FGY2WhTYpPnrIDTdsKH5` |
| Liam    | `TX3LPaxmHKxFdv7VOQHJ` |
| Lily    | `pFZP5JQG7iQjIQuC4Bku` |
| Matilda | `XrExE9yKIg1WjnnlVkGX` |
| River   | `SAz9YHcvj6GT2YYXdXww` |
| Roger   | `CwhRBWXzGAHq8TQ4Fs17` |
| Sarah   | `EXAVITQu4vr4xnSDxMaL` |
| Will    | `bIHbv24MWmeRgasZH58o` |

<br />