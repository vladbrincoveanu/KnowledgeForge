package dispatch

import "fmt"

const (
	sendGridEndpoint = "https://api.sendgrid.com/v3/mail/send"
	twilioEndpoint   = "https://api.twilio.com/2010-04-01/Accounts"
)

type ReceiptDispatcher struct {
	EmailProviderURL string
	SmsProviderURL   string
}

func NewReceiptDispatcher() ReceiptDispatcher {
	return ReceiptDispatcher{
		EmailProviderURL: sendGridEndpoint,
		SmsProviderURL:   twilioEndpoint,
	}
}

func (dispatcher ReceiptDispatcher) SendReceipt(channel string, recipient string) string {
	return fmt.Sprintf("sent %s receipt to %s", channel, recipient)
}
