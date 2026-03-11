import { Module } from '@nestjs/common';

import { PaymentsModule } from './payments/payments.module';

/**
 * Root module for the OmniPay mobile API gateway.
 */
@Module({
  imports: [PaymentsModule],
})
export class AppModule {}
