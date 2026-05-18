from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import JsonResponse
from .models import USBDevice, ClientPC, USBLog


class CheckUSBView(APIView):
    def post(self, request):
        pnp_id  = request.data.get('pnp_id')
        pc_name = request.data.get('pc_name')
        caption = request.data.get('caption')

        pc, _ = ClientPC.objects.get_or_create(pc_name=pc_name)

        usb, created = USBDevice.objects.get_or_create(
            pnp_id=pnp_id,
            defaults={'caption': caption, 'status': 'pending'}
        )

        if created:
            # Yangi qurilma — whitelist'da yo'q, bloklash
            USBLog.objects.create(
                pc=pc, usb_caption=caption, pnp_id=pnp_id,
                action="Yangi qurilma — bloklandi"
            )
            return Response({'status': 'pending'})

        if usb.status == 'allowed':
            # Whitelist'da bor — ruxsat
            USBLog.objects.create(
                pc=pc, usb_caption=caption, pnp_id=pnp_id,
                action="Whitelist — ruxsat berildi"
            )
            return Response({'status': 'allowed'})

        # pending yoki blocked
        USBLog.objects.create(
            pc=pc, usb_caption=caption, pnp_id=pnp_id,
            action=f"Bloklangan — status: {usb.status}"
        )
        return Response({'status': usb.status})


def ping(request):
    return JsonResponse({'ok': True})
