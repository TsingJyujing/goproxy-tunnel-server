# coding=utf-8
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.middleware.csrf import get_token
from django.shortcuts import render, redirect


def login_view(request):
    """
    Login Page
    :param request:
    :return:
    """
    if request.method == 'POST':
        # 请求为 POST，利用用户提交的数据构造一个绑定了数据的表单
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            print("User {} has login.".format(form.get_user()))
            try:
                next_page = request.GET["next"]
            except:
                next_page = "/"
            return redirect(next_page)
        else:
            print("User {} login failed.".format(form.get_user()))
    try:
        token = request.COOKIES['csrftoken']
    except:
        token = get_token(request)
    return render(request, 'login.html', context={
        "csrf_token": token
    })


@login_required
def proxy_manager(request):
    return render(request, "manage.html")
