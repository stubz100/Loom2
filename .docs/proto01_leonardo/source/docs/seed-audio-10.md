---
updatedAt: 2026-08-21T07:40:47.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Seed Audio 1.0

This guide shows how to generate speech using the Seed Audio 1.0 model via the Leonardo.AI REST API.

# Sample Request

```curl
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v2/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
    "model": "seed-audio-1.0",
    "public": false,
    "parameters": {
      "prompt": "Welcome back, traveller. The city gates close at sundown, so lets not waste any time.",
      "voice_id": "zh_female_vv_uranus_bigtts",
      "language_code": "en",
      "speed": 1,
      "pitch": 0,
      "volume": 1,
      "quantity": 1
    }
}
'
```

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

| Parameter                  | Type      | Definition                                                                                                                                                            |
| :------------------------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| guidances.audio\_reference | `array`   | Maximum 3 items. Each item includes audio.id and audio.type (`UPLOADED` or `GENERATED`). Each item must be at most 30 seconds and under 10 MB.                        |
| guidances.image\_reference | `array`   | Maximum 1 item. Each item includes image.image (with id and type), image.order, and image.strength (`LOW`, `MID`, or `HIGH`, defaults to `MID`). Must be under 10 MB. |
| language\_code             | `string`  | Language of the generated speech as an ISO 639-1 code. Set to `en`. Defaults to `en`.                                                                                 |
| model                      | `string`  | Specifies the model used for generation. Set to `seed-audio-1.0`.                                                                                                     |
| pitch                      | `number`  | Adjusts the pitch of the generated speech. Ranges from `-12` to `12`. Defaults to `0`.                                                                                |
| prompt                     | `string`  | Text to synthesize. Maximum of 3000 characters. Reference uploaded audio clips by order with `@Audio1`, `@Audio2`, `@Audio3`.                                         |
| public                     | `boolean` | Controls whether the generated audio is public (true) or private (false).                                                                                             |
| quantity                   | `number`  | The number of outputs to generate. Set to `1`, `2`, `3`, or `4`. Defaults to `1`.                                                                                     |
| speed                      | `number`  | Adjusts the playback speed of the generated speech. Ranges from `0.5` to `2`. Defaults to `1`.                                                                        |
| voice\_id                  | `string`  | ID of the preset voice used for speech. See List of Voice IDs below.                                                                                                  |
| volume                     | `number`  | Adjusts the volume of the generated speech. Ranges from `0.5` to `2`. Defaults to `1`.                                                                                |

## List of Voice IDs

The API accepts the following `voice_id` values:

| Voice ID                                  |
| :---------------------------------------- |
| `id_female_bv161narration_uranus_bigtts`  |
| `zh_female_cancan_uranus_bigtts`          |
| `zh_female_jitangnv_uranus_bigtts`        |
| `zh_female_kefunvsheng_uranus_bigtts`     |
| `zh_female_liuchangnv_uranus_bigtts`      |
| `zh_female_meilinvyou_uranus_bigtts`      |
| `zh_female_mizai_uranus_bigtts`           |
| `zh_female_sajiaoxuemei_uranus_bigtts`    |
| `zh_female_tianmeixiaoyuan_uranus_bigtts` |
| `zh_female_vv_uranus_bigtts`              |
| `zh_female_xiaohe_uranus_bigtts`          |
| `zh_female_xiaoxue_uranus_bigtts`         |
| `zh_female_yingyujiaoxue_uranus_bigtts`   |
| `zh_male_dayi_uranus_bigtts`              |
| `zh_male_liufei_uranus_bigtts`            |
| `zh_male_m191_uranus_bigtts`              |
| `zh_male_ruyayichen_uranus_bigtts`        |
| `zh_male_sophie_uranus_bigtts`            |
| `zh_male_sunwukong_uranus_bigtts`         |
| `zh_male_taocheng_uranus_bigtts`          |