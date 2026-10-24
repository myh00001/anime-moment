"""Select one reporter from the options frozen at capture time."""
def generate_report(photo,options,root,local):
    if options.get('ai_report',False) and options.get('report_provider','local')=='deepseek':
        from report_cloud import make_cloud_report
        return make_cloud_report(photo,root)
    return local(photo,options.get('ai_report',False))
