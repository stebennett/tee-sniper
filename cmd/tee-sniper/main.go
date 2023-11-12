package main

import (
	"log"

	env "github.com/Netflix/go-env"
	"github.com/stebennett/tee-sniper/pkg/client"
)

type Environment struct {
	Username string `env:"TS_USERNAME,required=true"`
	Pin      string `env:"TS_PIN,required=true"`
	BaseUrl  string `env:"TS_BASEURL,required=true"`
}

func main() {
	var environment Environment

	_, err := env.UnmarshalFromEnviron(&environment)
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("%s", environment)

	wc, err := client.NewClient(environment.BaseUrl)
	if err != nil {
		log.Fatal(err)
	}

	ok, err := wc.Login(environment.Username, environment.Pin)
	if err != nil {
		log.Fatal(err)
	}

	log.Printf("login status: %t", ok)
}
