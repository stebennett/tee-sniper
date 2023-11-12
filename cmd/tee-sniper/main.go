package main

import (
	"log"

	env "github.com/Netflix/go-env"
)

type Environment struct {
	Username string `env:"TS_USERNAME,required=true"`
	Pin      string `env:"TS_PIN,required=true"`
}

func main() {
	var environment Environment

	_, err := env.UnmarshalFromEnviron(&environment)
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("%s", environment)
}
