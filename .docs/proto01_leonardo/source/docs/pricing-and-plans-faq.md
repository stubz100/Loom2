---
updatedAt: 2026-09-01T04:00:45.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Pricing & Plans FAQs

Answers to frequently asked questions relating to Pricing & Plans

<Callout icon="📘" theme="info">
  **New to Pay-As-You-Go?** Read our comprehensive [Pay As You Go Guide](/docs/payg-guide) to understand how it works and how to migrate.
</Callout>

## Getting Started with Pay-As-You-Go (PAYG)

### How do I get started with the Leonardo AI API?

You can get started immediately by creating an API account from the <Anchor target="_blank" href="https://app.leonardo.ai/api-access">API Access</Anchor> tab.

***

### What is the pricing model for the API?

The API is priced on a Pay-As-You-Go basis, with no upfront commitment or monthly fees. You only pay for what you use and can scale usage up or down at any time.

***

### What is the API pricing calculator?

The API pricing calculator helps you estimate the cost of your Leonardo AI Production API requests before you run them. You can use it to:

* Preview the cost of a generation request based on the models and features you select
* See how changes to resolution, output count, etc. affect pricing
* Decide reasonable auto top-up thresholds and amounts
* Plan and manage your spend under the Pay-As-You-Go model

The calculator is available in the <Anchor target="_blank" href="https://app.leonardo.ai/api-access/pricing-calculator">API section of the Leonardo App</Anchor> and provides clear, upfront visibility into pricing estimates so you can test, launch, and scale with confidence.

***

### How is API usage billed?

API usage is calculated based on the models and features you use (such as image generation or training). Usage costs are deducted from your account balance in real time.

***

### How do I add credit to my account?

You can add credit to your account at any time through manual top ups in the <Anchor target="_blank" href="https://app.leonardo.ai/api-access">API Access</Anchor> tab. Top-ups must be made in whole amounts, and your available balance will be updated immediately.

***

### Can I enable automatic top-ups?

Yes, you can enable automatic top-ups by setting:

* A top-up threshold that triggers a top-up (e.g., when balance drops below $50)
* A top-up amount to be added when the threshold is reached (e.g., add $100)

You can view, edit, or disable auto top-ups at any time in the [API Access](https://app.leonardo.ai/api-access) tab.

***

### Does my account balance expire?

No, your account balance does not expire.

***

### What happens if my balance runs out?

If your balance reaches zero, API requests will pause until additional credit is added. You'll see clear messaging in the [API Access](https://app.leonardo.ai/api-access) tab. To avoid service interruptions, enable auto top-ups in your account settings.

***

### Are discounts available?

Discounts are not applied by default for self-serve users. Custom pricing and per-model discounts are available for eligible customers by contacting our team via the Custom Deals contact us form on the [API Access](https://app.leonardo.ai/api-access) Tab, or via general Customer Support.

***

### How do I get a custom or enterprise pricing plan?

If you have high-volume usage, require dedicated infrastructure, or want custom per-model discounts, please contact our team via the Custom Deals contact us form on the [API Access](https://app.leonardo.ai/api-access) Tab, or via general Customer Support, to discuss a tailored plan.

***

## Migrating to Pay-As-You-Go (PAYG)

### What is changing with API pricing?

Leonardo AI is transitioning from subscription plans to a Pay-As-You-Go (PAYG) pricing model. Instead of a fixed recurring charge, you load credit as required via manual top-ups or automatically via auto top-Ups.

***

### When does this change take effect?

PAYG pricing is available now for new users. Existing customers can switch at any time by cancelling their subscription, after which they'll be automatically moved to PAYG and their remaining credits converted into a non-expiring credit balance.

***

### How do I switch to Pay-As-You-Go (PAYG)?

Existing API customers can switch to the Pay-As-You-Go pricing model at any time by following these steps:

1. Go to the [API Access](https://app.leonardo.ai/api-access) tab in your Leonardo AI account
2. Navigate to your current API subscription
3. Cancel your monthly subscription
4. Your account is automatically transitioned to the PAYG pricing model
5. Any remaining API credits are converted into a credit balance in your PAYG account
6. Your credit balance does not expire and can be used immediately

There is no downtime during the transition, and you can continue using the API immediately.

***

### What happens to my current subscription plan?

Your current subscription will remain unchanged until you decide to migrate to PAYG.

***

### Will PAYG be more expensive than my current plan?

PAYG pricing is usage-based, so your costs scale with how much you use the API. For many users, this offers better cost control and transparency compared to a fixed subscription. Use the API pricing calculator to compare your expected costs.

***

### Do I lose any features when switching to PAYG?

No, you retain access to all the same API features and models when switching to Pay-As-You-Go.

***

### What happens to my custom pricing agreement?

If you have a custom pricing agreement, your current terms remain unchanged. A Leonardo team member will contact you directly to discuss your plan before any changes are made.

***

### Are there any changes to API responses?

Yes. Generation responses now include a `cost` object showing the amount charged and the unit (dollars or credits), providing clearer visibility into costs. The `apiCreditCost` field remains during the transition period.

***

### Who can I contact if I have questions about pricing or migration?

If you have questions about pricing, migration timing, or custom plans, please contact our Customer Support Team or reach out to your Leonardo AI account manager.

***