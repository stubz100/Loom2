---
updatedAt: 2026-07-09T02:47:56.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Deprecations & Changes

As the Leonardo AI API evolves with new models, features, and improvements, we occasionally retire older ones. Some changes are driven by updates we make to the Leonardo API, while others reflect changes made by third-party model providers whose models are available through our platform.

This page lists all deprecations in reverse chronological order, with the most recent announcements at the top.

<br />

## July 9, 2026 — Sora 2 and Sora 2 Pro retired July 9, 2026

Sora 2 (sora-2) and Sora 2 Pro (sora-2-pro) are no longer available via the Leonardo API. This is a provider-driven change.

**Action required:** Update your API requests to use veo-3.1-fast-generate-001 / veo-3.1-generate-001 immediately.

## June 4, 2026 — Motion 1.0 retiring June 17, 2026

Motion 1.0 (svd) will no longer be available via the Leonardo API, web app, or mobile apps after Wednesday, June 17, 2026 at 9:30 AM AEST (UTC+10). We're consolidating our video model lineup.

**Replacement**: We recommend switching to <Anchor target="_blank" href="https://docs.leonardo.ai/docs/hailuo-23">Hailuo 2.3 </Anchor>(hailuo-2\_3).

**Action required**: Update your API requests to use <Anchor target="_blank" href="https://docs.leonardo.ai/docs/hailuo-23">hailuo-2\_3</Anchor> before June 17, 2026.

***

## June 1, 2026 — Veo 3 and Veo 3 Fast retiring June 29, 2026

Veo 3 and Veo 3 Fast will no longer be available via the Leonardo API after June 29, 2026. The provider, Google, is retiring both these models.

**Replacement**: We recommend switching to Veo 3.1 and Veo 3.1 Fast which offer improved quality.

**Action required**: Update your API requests to use [Veo 3.1](https://docs.leonardo.ai/docs/veo-31) or Veo 3.1 Fast before June 29, 2026. Note that the latest version of our API docs on both these models can be found <Anchor target="_blank" href="https://docs.leonardo.ai/v2.0/reference/creategeneration-1">here</Anchor>.

***

## May 5, 2026 — Veo preview aliases retiring May 13, 2026

The Veo preview model aliases will no longer be accepted via the Leonardo API after May 13, 2026. After this date, any requests using a `-preview` model name will fail.

| Sunset Date  | What's Changing       | Replacement                 | Affected Alias                  |
| ------------ | --------------------- | --------------------------- | ------------------------------- |
| May 13, 2026 | Preview alias removal | `veo-3.0-generate-001`      | `veo-3.0-generate-preview`      |
| May 13, 2026 | Preview alias removal | `veo-3.0-fast-generate-001` | `veo-3.0-fast-generate-preview` |
| May 13, 2026 | Preview alias removal | `veo-3.1-generate-001`      | `veo-3.1-generate-preview`      |
| May 13, 2026 | Preview alias removal | `veo-3.1-fast-generate-001` | `veo-3.1-fast-generate-preview` |

**Action required:** Update your API requests to use the `001` model names before **May 13, 2026**. All `001` models are available now and are functionally identical to their preview counterparts: this is a naming alias change only.

***

## May 1, 2026 — Seedance 1.0 Lite retiring May 13, 2026

Seedance 1.0 Lite will no longer be available via the Leonardo API after May 13, 2026.

**Replacement**: We recommend switching to <Anchor target="_blank" href="https://docs.leonardo.ai/docs/seedance-1-0-pro">Seedance 1.0 Pro Fast</Anchor> — it uses the same parameter shape as 1.0 Lite, so migration is a simple model ID swap, with better latency and overall efficiency. <Anchor target="_blank" href="https://docs.leonardo.ai/docs/seedance-20">Seedance 2.0</Anchor> is also available as a premium alternative.

**Action required**: Update your API requests to use seedance-1.0-pro-fast (or seedance-2.0) before May 13, 2026. See the <Anchor target="_blank" href="https://docs.leonardo.ai/docs/seedance-1-0-pro">Seedance 1.0 Pro guide</Anchor> or <Anchor target="_blank" href="https://docs.leonardo.ai/docs/seedance-20">Seedance 2.0</Anchor> guide for usage details.

***

## April 20, 2026 — `mode` parameter retiring May 4, 2026

The `mode` parameter for [GPT Image-1.5](https://docs.leonardo.ai/docs/gpt-image-1-5) and [Ideogram 3.0](https://docs.leonardo.ai/docs/ideogram-30) generations is being retired on **May 4, 2026**. Use the `quality` parameter instead. After May 4, any requests that include `mode` will fail.

| Sunset Date | What's Changing  | Replacement         | Affected Models                                                                                                         |
| ----------- | ---------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| May 4, 2026 | `mode` parameter | `quality` parameter | [GPT Image-1.5](https://docs.leonardo.ai/docs/gpt-image-1-5), [Ideogram 3.0](https://docs.leonardo.ai/docs/ideogram-30) |

**What you need to do:** Replace `mode` with `quality` in your API requests before May 4, 2026. The accepted values for GPT Image-1.5 (`LOW`, `MEDIUM`, `HIGH`). For Ideogram 3.0 (`TURBO`, `BALANCED`, `QUALITY`)

### Migration example

**Before (deprecated):**

```json
{
  "model": "gpt-image-1.5",
  "parameters": {
    "mode": "QUALITY",
    "prompt": "A serene mountain landscape at dawn"
  }
}
```

**After (current):**

```json
{
  "model": "gpt-image-1.5",
  "parameters": {
    "quality": "HIGH",
    "prompt": "A serene mountain landscape at dawn"
  }
}
```

No other request changes are needed. For full model documentation, see [GPT Image-1.5](https://docs.leonardo.ai/docs/gpt-image-1-5) and [Ideogram 3.0](https://docs.leonardo.ai/docs/ideogram-30).

***

## Need Help?

If you have questions about an upcoming deprecation or need assistance migrating, contact our support team via the Intercom widget on the [Leonardo.Ai app](https://app.leonardo.ai/) — select **Ask a question** then **API Help**. You can also email us at <support@leonardo.ai>.