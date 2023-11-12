package client

import (
	"fmt"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"strings"

	"github.com/PuerkitoBio/goquery"
)

var (
	loginUrl = "login.php"
)

type WebClient struct {
	baseUrl    string
	httpClient *http.Client
}

func NewClient(u string) (*WebClient, error) {
	jar, err := cookiejar.New(nil)
	if err != nil {
		return nil, err
	}

	client := &http.Client{
		Jar: jar,
	}

	return &WebClient{
		baseUrl:    u,
		httpClient: client,
	}, nil
}

func (w WebClient) Login(username string, password string) (bool, error) {
	form := url.Values{}
	form.Add("task", "login")
	form.Add("topmenu", "1")
	form.Add("memberid", username)
	form.Add("pin", password)
	form.Add("cachemid", "1")
	form.Add("Submit", "Login")

	url := fmt.Sprintf("%s%s", w.baseUrl, loginUrl)

	req, err := http.NewRequest("POST", url, strings.NewReader(form.Encode()))
	if err != nil {
		return false, err
	}

	req.Header.Add("Content-Type", "application/x-www-form-urlencoded")

	resp, err := w.httpClient.Do(req)
	if err != nil {
		return false, err
	}

	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return false, nil
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return true, err
	}

	pageTitle := doc.Find("title").Text()
	return strings.HasPrefix(pageTitle, "Welcome"), nil
}
