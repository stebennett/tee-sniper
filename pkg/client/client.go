package client

import (
	"fmt"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"strings"

	"github.com/PuerkitoBio/goquery"
	"github.com/stebennett/tee-sniper/pkg/models"
)

var (
	loginUrl        = "login.php"
	teeAvailability = "memberbooking/"
	book            = "memberbooking/"
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

func (w WebClient) GetCourseAvailability(dateStr string) ([]models.TimeSlot, error) {
	slots := []models.TimeSlot{}

	url := fmt.Sprintf("%s%s", w.baseUrl, teeAvailability)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return slots, err
	}

	q := req.URL.Query()
	q.Add("date", dateStr)
	req.URL.RawQuery = q.Encode()

	resp, err := w.httpClient.Do(req)
	if err != nil {
		return slots, err
	}

	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return slots, fmt.Errorf("invalid status code returned %d", resp.StatusCode)
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return slots, err
	}

	doc.Find("tr.canreserve,tr.cantreserve").Each(func(i int, s *goquery.Selection) {
		bookingButton := s.Find("a.inlineBooking").Length() != 0
		peopleBooked := s.Find("td.tbooked").Length() == 0
		blocked := s.Find("td.tblocked").Length() != 0
		time := s.Find("th").Text()

		bookingForm := make(map[string]string)
		s.Find("td form > input").Each(func(i int, q *goquery.Selection) {
			name, nok := q.Attr("name")
			value, vok := q.Attr("value")
			if nok && vok {
				bookingForm[name] = value
			}
		})

		if peopleBooked && !blocked && bookingButton {
			slots = append(slots, models.TimeSlot{
				Time:        time,
				BookingForm: bookingForm,
				CanBook:     bookingButton,
			})
		}
	})

	return slots, nil
}

func (w WebClient) BookTimeSlot(timeSlot models.TimeSlot) (bool, error) {
	url := fmt.Sprintf("%s%s", w.baseUrl, book)
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return false, err
	}

	q := req.URL.Query()
	q.Add("numslots", "4")

	for k, v := range timeSlot.BookingForm {
		q.Add(k, v)
	}

	req.URL.RawQuery = q.Encode()

	resp, err := w.httpClient.Do(req)
	if err != nil {
		return false, err
	}

	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return false, fmt.Errorf("invalid status code returned %d", resp.StatusCode)
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return false, err
	}

	confirmation := doc.Find("#globalwrap > div.user-messages.alert.user-message-success.alert-success > ul > li > strong").Text()
	return strings.Compare(confirmation, "Now please enter the names of your playing partners.") == 0, nil
}
