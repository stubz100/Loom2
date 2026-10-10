---
updatedAt: 2025-09-03T05:59:07.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Guide to Concurrency, Queue, and Rate Limit

Understanding Leonardo API's concurrency, queue/pending limits, and rate limits

When planning to use the Leonardo API in production at scale, it is important to understand the differences between the following key concepts:

* **Concurrency** — the number of image or video generation jobs that can be processed in parallel.
* **Queue/Pending Limit** — the maximum number of requests allowed to wait for processing when all concurrent slots are occupied.
* **API Rate Limit** — the maximum number of API requests that can be made in a given time period.

## The Restaurant Metaphor

If Leonardo's API service were a restaurant, and generation jobs like image generation, video generation, upscaling, etc. were meals or dishes, then:

* **Concurrency** is the number of cooking stations.\
  Concurrency refers to the number of active kitchen stations or stoves, each able to prepare a dish simultaneously. For example, if there are 10 cooking stations, the kitchen can work on 10 meals at the same time. When all stations are occupied, new orders must wait their turn.
* **Queue/Pending Limit** is the number of dish orders accepted by the kitchen.\
  This limit represents how many dish orders the kitchen will accept and keep in line for cooking when all stations are busy. If the queue is full, say 50 waiting orders, the kitchen won’t take more orders until some are finished — similar to a busy restaurant temporarily stopping new orders when overwhelmed.
* **API Rate Limit** is waiter capacity for taking orders from tables.\
  The rate limit is like how many waiters are available to take new orders from the dining area. Each waiter can only write down and pass on a certain number of orders per minute before becoming overwhelmed. If too many orders come in at once, some must wait for the next round.

| Concept             | Technical Definition                            | Restaurant Metaphor                           |
| :------------------ | :---------------------------------------------- | :-------------------------------------------- |
| Concurrency         | Number of parallel generation jobs              | Number of cooking stations                    |
| Queue/Pending Limit | Number of pending generation jobs               | Number of orders accepted by kitchen waitlist |
| API Rate Limit      | Number of API requests within a given timeframe | Waiter capacity or availability               |

## Default Limits

Leonardo.Ai's default concurrency, queue limit, rate limits are documented [here](https://docs.leonardo.ai/reference/limits). These limits can be customized with a Custom API Plan by reaching out via [Leonardo's contact form](https://leonardo.ai/contact-us/).

To help size your plan correctly, please share the following information:

* How many images or videos do you anticipate generating per month?
* Do you expect occasional, spiky usage or predictable, steady demand?

> 📘 Leonardo API for Enterprise
>
> In addition to the Custom API Plan, Leonardo.Ai provides enterprise-grade, high-volume access by leveraging dedicated infrastructure that can support millions of active users. For advanced scalability or large-scale API deployment, contact our team through [Leonardo's contact form](https://leonardo.ai/contact-us/) for a tailored solution.

## Common Misconceptions

**Misconception 1:** *You can't make more than 10 image or video generation requests because the default concurrency is 10.*

Concurrency limits the number of generation jobs actively processed at the same time, like the number of cooking stations in a kitchen. You can submit many more requests; those beyond 10 will wait in a queue until a concurrency slot frees up.

**Misconception 2:** *I have more than 10 users accessing my app so I need more concurrency.*

The number of users does not automatically mean you need more concurrency. Imagine a kitchen with 10 stoves serving dozens or even hundreds of diners efficiently by processing orders as stoves become available. Requests simply queue and are handled as cooking stations free up.