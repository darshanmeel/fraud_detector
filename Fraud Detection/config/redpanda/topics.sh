#!/bin/bash
rpk topic create tx.raw.hot -p 16 --brokers redpanda:29092
rpk topic create tx.raw.cold -p 8 --brokers redpanda:29092
rpk topic create feature.update -p 8 --brokers redpanda:29092
rpk topic create decision.block -p 4 --brokers redpanda:29092
rpk topic create decision.allow -p 4 --brokers redpanda:29092
rpk topic create decision.review -p 4 --brokers redpanda:29092
rpk topic create decision.degraded -p 2 --brokers redpanda:29092
rpk topic create tx.dead-letter -p 2 --brokers redpanda:29092
