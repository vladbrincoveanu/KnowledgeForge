import { Injectable } from '@nestjs/common';

/**
 * Coordinates downstream OmniPay services for payment requests.
 */
@Injectable()
export class PaymentsService {
  /**
   * Return a demo payment status payload.
   */
  getPayment(transactionId: string) {
    return {
      transactionId,
      status: 'authorized',
      source: 'redis-cache',
    };
  }

  /**
   * Return a demo orchestration response.
   */
  authorize(payload: Record<string, unknown>) {
    return {
      transactionId: payload.transactionId ?? 'demo-transaction',
      riskCheck: 'requested',
      ledgerReservation: 'created',
      cardAuthorization: 'pending',
    };
  }
}
