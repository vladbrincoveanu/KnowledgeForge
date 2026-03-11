import { Body, Controller, Get, Param, Post } from '@nestjs/common';

import { PaymentsService } from './payments.service';

/**
 * Public HTTP endpoints exposed to the mobile apps.
 */
@Controller('payments')
export class PaymentsController {
  /**
   * Create a controller with the orchestration service dependency.
   */
  constructor(private readonly paymentsService: PaymentsService) {}

  /**
   * Get a cached payment status.
   */
  @Get(':transactionId')
  getPayment(@Param('transactionId') transactionId: string) {
    return this.paymentsService.getPayment(transactionId);
  }

  /**
   * Start a payment authorization flow.
   */
  @Post()
  authorize(@Body() payload: Record<string, unknown>) {
    return this.paymentsService.authorize(payload);
  }
}
