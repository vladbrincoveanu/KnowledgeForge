FROM rust:1.70 as builder
WORKDIR /build
COPY Cargo.toml .
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
COPY --from=builder /build/target/release/omnipay-rust-service /usr/local/bin/
EXPOSE 8080
CMD ["omnipay-rust-service"]
