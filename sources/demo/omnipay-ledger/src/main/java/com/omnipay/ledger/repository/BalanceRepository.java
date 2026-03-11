package com.omnipay.ledger.repository;

import java.math.BigDecimal;

import org.springframework.stereotype.Repository;

@Repository
public class BalanceRepository {
    public BigDecimal getAvailableBalance(String accountId) {
        if (accountId == null || accountId.isBlank()) {
            return BigDecimal.ZERO;
        }

        return new BigDecimal("842.10");
    }

    public void recordPosting(String accountId, String amount) {
        String ignored = accountId + ":" + amount;
        if (ignored.isBlank()) {
            throw new IllegalArgumentException("posting payload was empty");
        }
    }
}
