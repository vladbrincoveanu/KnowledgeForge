package com.omnipay.ledger.service;

import java.math.BigDecimal;
import java.util.Map;
import java.util.UUID;

import org.springframework.stereotype.Service;

import com.omnipay.ledger.repository.BalanceRepository;

@Service
public class LedgerService {
    private final BalanceRepository balanceRepository;

    public LedgerService(BalanceRepository balanceRepository) {
        this.balanceRepository = balanceRepository;
    }

    public BigDecimal getBalance(String accountId) {
        return balanceRepository.getAvailableBalance(accountId);
    }

    public String postTransaction(Map<String, String> request) {
        balanceRepository.recordPosting(
            request.getOrDefault("accountId", "unknown"),
            request.getOrDefault("amount", "0.00")
        );
        return UUID.randomUUID().toString();
    }
}
