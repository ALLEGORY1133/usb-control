from rest_framework.views import APIView
from rest_framework.response import Response
from .models import USBDevice, ClientPC, USBLog


class CheckUSBView(APIView):
    def post(self, request):
        pnp_id  = request.data.get('pnp_id', '').strip()
        pc_name = request.data.get('pc_name', '').strip()
        caption = request.data.get('caption', '').strip()

        if not pnp_id:
            return Response({'error': 'pnp_id yetishmaydi'}, status=400)

        # Kompyuterni topish yoki yaratish
        pc, _ = ClientPC.objects.get_or_create(pc_name=pc_name)

        # USB qurilmani topish yoki yaratish
        usb, created = USBDevice.objects.get_or_create(
            pnp_id=pnp_id,
            defaults={'caption': caption, 'status': 'pending', 'pc': pc}
        )

        if not created:
            # Mavjud qurilmani yangilash
            usb.caption   = caption
            usb.pc        = pc
            usb.save(update_fields=['caption', 'pc', 'last_seen'])

        # Log yozish
        USBLog.objects.create(
            pc=pc,
            usb_caption=caption,
            pnp_id=pnp_id,
            action=f"So'rov: {usb.status}"
        )

        return Response({'status': usb.status})
