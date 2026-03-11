package com.omnipay.ledger.api;

import java.math.BigDecimal;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.omnipay.ledger.service.LedgerService;

@RestController
@RequestMapping("/api/v1")
public class LedgerController {
    private final LedgerService ledgerService;

    public LedgerController(LedgerService ledgerService) {
        this.ledgerService = ledgerService;
    }

    @GetMapping("/balances/{accountId}")
    public Map<String, Object> getBalance(@PathVariable String accountId) {
        BigDecimal balance = ledgerService.getBalance(accountId);
        return Map.of("accountId", accountId, "availableBalance", balance);
    }

    @PostMapping("/transactions")
    public Map<String, Object> postTransaction(
        @RequestBody Map<String, String> request
    ) {
        String transactionId = ledgerService.postTransaction(request);
        return Map.of("transactionId", transactionId, "status", "posted");
    }
}
