FROM golang:1.26.1-alpine AS builder
WORKDIR /src
COPY go.mod .
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /out/go-policy ./main.go

FROM gcr.io/distroless/base-debian12:nonroot
WORKDIR /app
COPY --from=builder /out/go-policy /app/go-policy
USER nonroot:nonroot
EXPOSE 8091
ENTRYPOINT ["/app/go-policy"]
